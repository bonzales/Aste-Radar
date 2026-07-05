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

### ⚠️ Spike da fare PRIMA di scrivere lo scraper (rischio n.1)

Non è ancora verificato **come** il PVP risponda a uno scraper `httpx` semplice:
potrebbe esserci navigazione JS, token di sessione, o anti-bot. Primo passo di
implementazione = uno *spike* di mezza giornata:
1. Riprodurre a mano la ricerca immobili per "provincia = Venezia" e catturare
   la/le richieste HTTP reali (URL, parametri, header, eventuali token).
2. Verificare se la lista risultati è nell'HTML statico o caricata via JS/API.
3. Salvare l'HTML/JSON grezzo in `raw/` e decidere: httpx+BS basta, oppure serve
   un browser headless, oppure conviene partire dai gestori.

Finché lo spike non chiarisce questo, lo scraper non si progetta nel dettaglio.
(Coerente con §9.2: scraper = fixture + integrazione, non TDD a vuoto su HTML volatile.)

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

## Piano di attacco proposto (dopo l'ok)

1. Spike PVP (capire come risponde) → decidere fonte/tecnica.
2. `scraper.py` sulla ricerca geografica + fixture HTML in `raw/`.
3. Layer DB + idempotenza.
4. `notifier.py` (smoke test su Telegram).
5. `main.py` orchestrazione + fail loud.
6. Run manuale end-to-end, poi cron sul VPS.
