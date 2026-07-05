# Spec Fase 1 — MVP notifica grezza

Stato: **BOZZA da validare con l'utente** (2026-07-05). Nessun codice finché non
approvata. Riferimenti: CLAUDE.md §3, §4 (Fase 1), §5, §8.

## Obiettivo (e non-obiettivo)

**Fa**: ogni run trova i lotti NUOVI il cui immobile è nelle zone target e li
manda su Telegram con titolo, comune, prezzo base, data vendita, link. Idempotente,
fail loud.

**NON fa** (rimandato alle fasi 2–3): download perizie, OCR, estrazione LLM,
scoring. Nessun giudizio sul lotto: solo "esiste, è nuovo, è nella tua zona".

## Filtro: geografico, non per tribunale (decisione presa)

Si cerca per **ubicazione dell'immobile**. Zone target da `config/comuni.yaml`:
provincia di Venezia (intera) + comune di Treviso + comuni TV limitrofi (da
confermare). Il tribunale che gestisce la vendita è irrilevante ai fini del filtro.

## Fonte dati

- **Primaria**: Portale Vendite Pubbliche (pvp.giustizia.it), ricerca immobili per
  provincia/comune. Ufficiale, copre tutti i tribunali → coerente col filtro geografico.
- **Secondaria / fallback**: gestori (Astalegale, Aste Giudiziarie Inlinea) se il
  PVP risulta ostico da scrapare per queste zone.

### ✅ Spike PVP FATTO (2026-07-05) — dettagli in `research/pvp-api.md`

Esito: il PVP è **scrapeabile via API JSON**, senza auth né anti-bot sugli
endpoint di ricerca. NON serve browser headless né BeautifulSoup: si chiama l'API.

- Endpoint: `POST …/ric-ms/ricerca/vendite` (URL completo + config discovery in
  `pvp-api.md`), paginato, `sort=dataPubblicazione,desc` per i nuovi.
- Risposta JSON con `body.content[]`; ogni lotto ha `id` (dedup stabile),
  `descLotto`, `prezzoBaseAsta`, `dataVendita`, `indirizzo.{citta,provincia}`, e
  molti extra utili dopo (`disponibilita`, `categoriaLotto`, coordinate…).
- **Insidia geografica**: `regione`/`localita` come stringa NON filtrano; il
  filtro vero della UI usa coordinate+raggio (payload non replicato). Strategia
  adottata: `ricercaLibera:"<comune>"` + **filtro lato client** su
  `indirizzo.provincia` ∈ {Venezia, Treviso} (il testo libero è sporco: "Mogliano
  Veneto" pesca anche Macerata) + solo `IMMOBILE_RESIDENZIALE` + dedup per `id`.
- httpx basta (curl nello spike). Fixtures reali in `tests/fixtures/pvp/`.

(Coerente con §9.2: scraper = fixture + integrazione. Le fixture in
`tests/fixtures/pvp/` alimentano i test del parser senza ri-scaricare.)

## Identità del lotto e idempotenza

Serve una **chiave stabile** per deduplicare tra run (CLAUDE.md §3). Candidata:
`(fonte, id_esterno)` dove `id_esterno` = identificativo PVP del lotto/inserzione
(da confermare nello spike; in subordine hash dell'URL di dettaglio). Un lotto già
in DB non si re-inserisce; uno già notificato non si re-notifica.

## Schema DB minimo (SQLite, `db/aste.sqlite`)

Tabella `lotti` (solo campi Fase 1; le fasi dopo aggiungono colonne):

| campo             | tipo    | note                                            |
|-------------------|---------|-------------------------------------------------|
| id                | INTEGER | PK autoincrement                                |
| fonte             | TEXT    | "pvp" \| "astalegale" \| …                       |
| id_esterno        | TEXT    | identificativo stabile sulla fonte              |
| url               | TEXT    | pagina di dettaglio                             |
| comune            | TEXT    | ubicazione immobile                             |
| provincia         | TEXT    | sigla                                           |
| titolo            | TEXT    | descrizione breve del lotto                     |
| prezzo_base       | REAL    | € base d'asta (null se non parseabile)          |
| data_vendita      | TEXT    | ISO, se disponibile                             |
| prima_vista_il    | TEXT    | ISO, quando lo scraper l'ha visto la prima volta |
| notificato_il     | TEXT    | ISO, null = ancora da notificare                |
| raw_path          | TEXT    | percorso HTML grezzo in raw/                    |

Vincolo di unicità su `(fonte, id_esterno)`. "Da notificare" = righe con
`notificato_il IS NULL`.

## Formato notifica Telegram

Un messaggio per lotto nuovo:

```
🏠 <titolo>
📍 <comune> (<provincia>)
💶 Base: € <prezzo_base>
🗓 Vendita: <data_vendita>
🔗 <url>
```

Se un campo è `null` → riga omessa, mai inventato (§1.2).

## Fail loud (CLAUDE.md §1.4)

`main.py` racchiude il run in un try/except globale: su eccezione manda a Telegram
`⚠️ scansione fallita: <motivo sintetico>` e esce con codice ≠ 0 (per il cron/log).
Il silenzio non deve mai essere ambiguo tra "nessun lotto nuovo" e "scraper rotto".

## Rispetto della fonte (CLAUDE.md §1.5)

User-agent identificabile, un piccolo delay tra le richieste, nessun parallelismo
aggressivo. Salvare sempre l'HTML grezzo in `raw/` per ri-parsare offline.

## Moduli toccati in Fase 1

`scraper.py` (fetch + parse lista), un piccolo layer DB (dentro `main.py` o
`db.py`), `notifier.py` (invio Telegram), `main.py` (orchestrazione idempotente +
fail loud). `downloader.py`/`parser.py`/`extractor.py`/`scorer.py` NON in Fase 1.

## Parametri confermati con l'utente (2026-07-05)

1. **Telegram**: bot **dedicato** ad aste-radar (token/chat separati dal bot
   Kraken), ma riusando il codice del bot Kraken. → `config/secrets.env` avrà i
   suoi `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` propri.
2. **Comuni TV limitrofi**: confermati tutti e 7 (Mogliano Veneto, Preganziol,
   Casale sul Sile, Casier, Silea, Zero Branco, Quinto di Treviso), `attivo: true`
   in `config/comuni.yaml`.
3. **Cron**: giornaliero alle **07:00**.
4. **Tipologia**: solo **residenziale** (case/appartamenti). Box, commerciale,
   terreni esclusi. Coerente col flip abitativo + prezzo-valore.

## Piano di attacco (stato al 2026-07-05)

1. ~~Spike PVP~~ → **FATTO** (2026-07-05): API scoperta e verificata con dati
   reali. Dettagli in `research/pvp-api.md`. (La rete web era inizialmente
   bloccata; sbloccata dall'utente aprendo l'egress dell'ambiente.)
2. `scraper.py` sulla ricerca geografica → **PRONTO da scrivere**: endpoint,
   corpo, schema risposta e strategia noti; fixtures reali in `tests/fixtures/pvp/`.
3. ~~Layer DB + idempotenza~~ → **FATTO**: `src/models.py` (`Lotto`), `src/db.py`
   (`connect/init_db/upsert_lotto/lotti_da_notificare/segna_notificato`), test in
   `tests/test_db.py` (7 test verdi, coprono no-duplicati / no-re-notifica).
   Parti network-independent completate mentre lo spike è bloccato.
4. `notifier.py` (smoke test su Telegram) → da fare (bot dedicato).
5. `main.py` orchestrazione + fail loud → da fare.
6. Run manuale end-to-end, poi cron sul VPS (07:00).

### Checklist spike PVP (da eseguire sul VPS)

1. Aprire a mano la ricerca immobili del PVP per "provincia = Venezia" e, con gli
   strumenti di rete del browser, catturare la/le richieste reali: URL, metodo,
   parametri (provincia, comune, tipologia=residenziale), header, eventuali token.
2. Stabilire se la lista risultati è nell'HTML statico o caricata via JS/API
   (se JS → valutare l'endpoint JSON sottostante o un browser headless).
3. Individuare l'**identificativo stabile** del lotto per la deduplica
   (`id_esterno`): id procedura + n. lotto, o id inserzione PVP.
4. Salvare 2–3 pagine grezze (lista + dettaglio) in `raw/` come **fixture** per
   scrivere il parser di `scraper.py` offline.
5. Verificare che i nomi comune in `config/comuni.yaml` combacino con quelli del PVP.
