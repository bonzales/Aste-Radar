# pvp-api.md — come parlare col Portale Vendite Pubbliche

Esito dello **spike del 2026-07-05** (fixtures grezze in `raw/spike-2026-07-05/`).
Questa pagina è la fonte di verità per `src/scraper.py`. Se il portale cambia e lo
scraper si rompe, si riparte da qui.

## Sintesi (cosa sapere in 30 secondi)

- Il PVP **non è HTML statico**: è una single-page app Angular. I dati arrivano da
  **micro-servizi JSON**. Quindi NON si fa scraping del DOM: si chiama l'API.
- La ricerca vendite è una **POST** a un endpoint JSON, **senza autenticazione**,
  **senza captcha/anti-bot** su questi endpoint pubblici. Risponde `200` con JSON.
- Il campo **`id`** del lotto è l'identificativo stabile per la deduplica
  (`id_esterno` nel nostro DB).

## Endpoint di ricerca

```
POST https://pvp.giustizia.it/ric-496b258c-986a1b71/ric-ms/ricerca/vendite
     ?page=0&size=50&sort=dataPubblicazione,desc
Content-Type: application/json
Accept: */*
Body: { "tipoLotto": "IMMOBILI", "ricercaLibera": "<testo>", ... }
```

- **Paginazione**: query param `page` (0-based), `size`.
- **Ordinamento**: `sort=dataPubblicazione,desc` → i più recenti per primi.
  ESSENZIALE per trovare i lotti NUOVI ogni giorno.
- Risposta: `{ "messaggio": "...", "body": { "content": [ {lotto}, ... ],
  "totalElements": N, ... } }`. I lotti sono in **`body.content`**.

### ⚠️ Il pezzo di URL con l'hash può cambiare

`ric-496b258c-986a1b71/ric-ms` è il path del micro-servizio, e contiene un hash di
deploy. **Non hardcodarlo alla cieca**: va letto dalla config a runtime (sotto),
così se cambia lo scraper non si rompe.

### Config discovery (per non hardcodare gli URL)

Gli URL dei servizi si ricavano da un endpoint di configurazione:

```
GET https://pvp.giustizia.it/bo-5897bc47-986a1b71/bo-ms/fe-config/it
```

Restituisce (fixture: `raw/spike-2026-07-05/fe-config-it.json`):

```json
{ "host": "https://pvp.giustizia.it",
  "msUrl": { "ricerca": "ric-496b258c-986a1b71/ric-ms",
             "vendite": "ve-3f723b85-986a1b71/ve-ms", ... } }
```

Base ricerca = `host + "/" + msUrl.ricerca`; endpoint = `<base>/ricerca/vendite`.
La base `bo-ms` iniziale si legge dall'attributo `config` dei widget nella pagina
(es. `home.html`: `systemParams.api["bo-ms"].url` = `/bo-5897bc47-986a1b71/bo-ms`).
Anche questa base ha un hash → in caso di rottura, ri-ispezionare l'HTML di una
pagina (`https://pvp.giustizia.it/pvp/`).

## Corpo della ricerca (campi del filtro)

Nomi campo accettati (dal FormGroup dell'app; fixture `lista-annunci.js`):

```
tipoLotto           es. "IMMOBILI"  (altri: MOBILI, AZIENDE, VALORI/CREDITI, ALTRO)
ricercaLibera       testo libero (match ampio: indirizzo E descrizione)
coordIndirizzo      punto geografico (usato dalla UI con Google Maps) + raggioAzione
textIndirizzo       etichetta indirizzo
raggioAzione        raggio in km (default 25)
regione, localita   presenti nel form ma NON filtrano se passati come stringa
prezzoBaseAstaDa/A  range prezzo
disponibilita       stato occupazione
anno, tribunale, procedura, numeroInserzione
```

### ⚠️ Come filtrare per la NOSTRA area (province VE/TV) — insidia chiave

- `regione`/`localita` passati come **stringa vengono ignorati** (test: totale
  invariato 281.408). Il filtro geografico "vero" della UI usa `coordIndirizzo`
  (lat/lon da Google Maps) + `raggioAzione`: formato del payload NON banale da
  replicare via API (non ricavato nello spike).
- `ricercaLibera: "<comune>"` **restringe molto** ma è un **match testuale ampio
  e sporco**: es. `"Mogliano Veneto"` → 40 risultati in provincia di **Macerata**
  (c'è Mogliano nelle Marche); `"Mestre"` → anche Palermo/Rovigo; `"Treviso"` →
  anche Roma/Milano. Quindi da solo NON basta.

**Strategia adottata per lo scraper** (robusta e semplice):
1. Per ogni comune target, `POST` con `ricercaLibera: "<comune>"`,
   `sort=dataPubblicazione,desc`, paginando finché servono i nuovi.
2. **Filtro lato client OBBLIGATORIO**: tieni solo i lotti con
   `indirizzo.provincia` ∈ {Venezia, Treviso} **e** comune coerente col target.
3. **Solo residenziale**: tieni `categoriaLotto == "IMMOBILE_RESIDENZIALE"`
   (filtro lato client; funziona bene).
4. **Dedup** per `id` (un lotto può uscire da più query).

Per "tutta la provincia di Venezia" serve l'elenco dei comuni VE in
`config/comuni.yaml` (insieme finito e noto), oppure — miglioria futura — capire il
payload `coordIndirizzo` catturando la XHR reale della UI (richiede browser via
proxy; non fatto nello spike).

## Schema del lotto (risposta) → mapping al nostro modello

Campi utili di ogni elemento di `body.content` (fixture:
`raw/spike-2026-07-05/sample-ricerca-mestre.json`, esempio `id=1738450`):

| Campo PVP            | Esempio                          | Nostro `Lotto` (Fase 1) |
|----------------------|----------------------------------|-------------------------|
| `id`                 | `1738450`                        | `id_esterno` (dedup)    |
| `descLotto`          | "Appartamento ubicato…"          | `titolo`                |
| `prezzoBaseAsta`     | `513000.0`                       | `prezzo_base`           |
| `dataVendita`        | `"2022-11-04"`                   | `data_vendita`          |
| `indirizzo.citta`    | `"Livorno"`                      | `comune`                |
| `indirizzo.provincia`| `"Livorno"`                      | `provincia` (+ filtro)  |
| (link costruito)     | vedi sotto                        | `url`                   |

Campi extra già disponibili (utili per Fase 3, da NON buttare): `categoriaLotto`,
`categoriaBene[]`, `dataPubblicazione`, `offertaMinima`, `rialzoMinimo`,
`disponibilita[]` (es. `["LIBER",…]` = libero → occupazione!), `numeroLotto`,
`procedura`, `tribunale`, `codiceTribunale`, `indirizzo.coordinate`.

### Link alla pagina di dettaglio (per la notifica)

```
https://pvp.giustizia.it/pvp/it/detail_annuncio.page?idAnnuncio=<id>
```

Verificato `200`. Da qui l'umano apre il lotto e (Fase 2) si scaricano gli allegati.

## Rispetto della fonte (CLAUDE.md §1.5)

- User-agent identificabile (usato nello spike:
  `aste-radar/0.1 (uso personale; info@chiriba.com)`).
- `size` ragionevole, piccola pausa tra le richieste, nessun parallelismo
  aggressivo. Salvare sempre il JSON grezzo in `raw/` per ri-parsare offline.

## Note operative

- Totale immobili a livello nazionale ≈ **281.408** → filtrare SEMPRE, mai paginare
  tutto.
- Gli endpoint `ric-ms` (ricerca) rispondono senza auth; `ve-ms` (vendite) ha
  restituito `401` sul path ricerca → per la ricerca si usa **`ric-ms`**.
- Browser headless (Playwright/Chromium) in questo ambiente NON raggiunge il PVP
  (non passa dal proxy): lo spike è stato fatto via `curl`, che rispetta il proxy.
