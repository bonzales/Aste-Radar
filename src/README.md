# src/ — la pipeline

Ordine del ciclo giornaliero (CLAUDE.md §3): **ingest → extract → score → notify**.

| Modulo          | Responsabilità                                              | Disciplina (§9.2)         |
|-----------------|-------------------------------------------------------------|---------------------------|
| `scraper.py`    | Fetch lotti nuovi dai portali; isola SOLO i nuovi vs DB      | fixture HTML + integrazione |
| `downloader.py` | Scarica allegati in `raw/<data>/<id_lotto>/`                | fixture + integrazione    |
| `parser.py`     | Estrae testo dalla perizia; OCR (pdftoppm+Tesseract)        | **TDD pieno**             |
| `extractor.py`  | LLM: testo perizia → JSON strutturato; campi mancanti `null`| **TDD pieno**             |
| `scorer.py`     | Applica `config/scoring.yaml`; punteggio + motivazione      | **TDD pieno**             |
| `notifier.py`   | Invia su Telegram i lotti sopra soglia                      | smoke test                |
| `main.py`       | Orchestratore, lanciato da cron; idempotente                | integrazione              |

I moduli **non esistono ancora**: si creano fase per fase (CLAUDE.md §4), non
tutti insieme. La Fase 1 (MVP notifica grezza) tocca `scraper`, un DB minimo,
`notifier` e `main` — nessuna analisi. `parser`/`extractor`/`scorer` arrivano
nelle Fasi 2–3.

Regole trasversali:
- **Idempotenza** (§3): rilanciare lo stesso giorno non duplica né re-notifica.
- **Fail loud** (§1.4): scansione fallita → alert Telegram esplicito.
- **Fonte grezza immutabile** (§1.1): `raw/` non si sovrascrive mai.
- **Selettori HTML in un punto solo** (§8): `scraper.py`, per riparare in fretta.
