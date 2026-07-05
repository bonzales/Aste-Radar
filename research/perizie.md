# perizie.md — pattern e insidie delle perizie

Conoscenza operativa per `parser.py` (OCR/testo) ed `extractor.py` (testo→JSON).
Si arricchisce con l'esperienza sulle perizie reali. Principio guida (CLAUDE.md
§1.2): **estrazione tracciabile, mai inventata** — se un dato non è nella perizia,
il campo resta `null`. Un numero falso in perizia può costare decine di migliaia
di euro in asta.

## Campi target dell'estrazione (CLAUDE.md §3.2)

```json
{
  "valore_stima": null,
  "prezzo_base": null,
  "superficie_mq": null,
  "indirizzo": null,
  "zona": null,
  "occupazione": null,
  "categoria_catastale": null,
  "difformita": null,
  "arretrati_condominiali": null,
  "note": null
}
```

Ogni campo deve poter essere ritracciato al file grezzo in `raw/` che l'ha
generato (CLAUDE.md §1.1).

## Insidie note (da popolare sul campo)

- **Scansioni vs PDF nativo** — molte perizie sono scansioni: servono
  `pdftoppm` + Tesseract (CLAUDE.md §7). Il testo nativo, se c'è, è più affidabile:
  provarlo prima di ricorrere all'OCR.
- **Valore di stima vs prezzo base** — non confonderli: la stima è il valore
  peritale; il prezzo base è la soglia d'asta corrente (già ribassata). Lo sconto
  che conta è prezzo base / valore di stima.
- **Superficie: commerciale vs calpestabile** — le perizie mescolano superficie
  lorda, commerciale, calpestabile. Annotare quale si estrae per non falsare i €/mq.
- **Occupazione** — cercare esplicitamente lo stato (libero / occupato dal
  debitore / contratto opponibile con data certa). È un criterio hard (§11).
- **Difformità/abusi** — spesso in sezioni dedicate ("conformità edilizia/
  urbanistica/catastale"). Sanabile vs insanabile cambia tutto.

## Onestà tecnica (CLAUDE.md §10)

Il parsing regex su perizie eterogenee è fragile: l'estrazione robusta passa per
LLM (`extractor.py`). Non nascondere la fragilità di un approccio: proporre
l'alternativa. Le perizie campione salvate in `tests/` sono le fixture per il TDD
di `parser.py`/`extractor.py` (§9.2).
