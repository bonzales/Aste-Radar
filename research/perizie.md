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
  provarlo prima di ricorrere all'OCR. **CONFERMATO sul campo (2026-07-05)**: la
  prima perizia scaricata (lotto 4604105, Venezia-Giudecca) è una scansione pura
  (0 caratteri nativi su 89 pagine) → OCR obbligatorio. `src/parser.py` decide
  pagina-per-pagina (nativo se c'è, altrimenti OCR ita).
- **Pagine di firma/timbro digitale** — l'OCR le rende come "rumore" (caratteri
  sparsi). Normale: le pagine di contenuto (stima, descrizione) escono pulite.
  L'estrattore LLM tollera bene questo rumore. Non tentare di ripulirlo a regex.
- **La perizia può includere allegati eterogenei** — il PDF "perizia" spesso
  contiene anche planimetrie, visure, foto: l'estrazione LLM va guidata a cercare
  i dati chiave in tutto il testo, non solo nelle prime pagine.
- **Valore di stima vs prezzo base** — non confonderli: la stima è il valore
  peritale; il prezzo base è la soglia d'asta corrente (già ribassata). Lo sconto
  che conta è prezzo base / valore di stima.
- **Superficie: commerciale vs calpestabile** — le perizie mescolano superficie
  lorda, commerciale, calpestabile. Annotare quale si estrae per non falsare i €/mq.
- **Occupazione** — cercare esplicitamente lo stato (libero / occupato dal
  debitore / contratto opponibile con data certa). È un criterio hard (§11).
- **Difformità/abusi** — spesso in sezioni dedicate ("conformità edilizia/
  urbanistica/catastale"). Sanabile vs insanabile cambia tutto.

## Modello LLM (DECISO 2026-07-05)

Estrazione di massa con **Haiku 4.5** (economico, coerente con CLAUDE.md §7), con
**escalation** a un modello più forte (Sonnet 5 / Opus 4.8) solo sui casi difficili.
Trigger di escalation da definire sul campo, es.: troppi campi tornati `null` su una
perizia che chiaramente li contiene, output non conforme allo schema JSON, bassa
confidenza. L'escalation NON deve mai portare a inventare dati (§1.2): se il modello
forte non trova il dato, resta `null`.

## Onestà tecnica (CLAUDE.md §10)

Il parsing regex su perizie eterogenee è fragile: l'estrazione robusta passa per
LLM (`extractor.py`). Non nascondere la fragilità di un approccio: proporre
l'alternativa. Le perizie campione salvate in `tests/` sono le fixture per il TDD
di `parser.py`/`extractor.py` (§9.2).
