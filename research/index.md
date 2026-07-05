# research/ — wiki di dominio (LLM-Wiki, Karpathy)

Conoscenza di dominio **persistente** del progetto `aste-radar`. L'agente la legge
prima di scrivere codice (CLAUDE.md §10). Non è documentazione per l'umano —
quella sta in `docs/` (Diátaxis). Qui vive ciò che serve all'agente per non fare
danni sulle aste e per non re-inventare ciò che è già stato deciso.

## Mappa

- [`log.md`](./log.md) — log append-only, greppabile, delle sessioni. **Leggi
  questo per primo** insieme a questo index. Ogni sessione produttiva aggiunge
  una riga (data · cosa fatto · cosa imparato).
- [`scoring.md`](./scoring.md) — razionale della griglia: PERCHÉ quei pesi e
  quelle soglie. Fa da contraltare a `config/scoring.yaml` (che dice solo i numeri).
- [`comuni.md`](./comuni.md) — note per microzona nel distretto di Venezia. Qui
  vive il vantaggio informativo dell'utente (residente).
- [`perizie.md`](./perizie.md) — pattern ricorrenti nelle perizie, insidie di
  parsing e OCR, formati ostici incontrati.
- [`fiscale.md`](./fiscale.md) — note fisco: prezzo-valore, plusvalenza <5 anni,
  flip, P.IVA, costi accollati. Alimenta la griglia, non la sostituisce.

## Come si usa

- **All'inizio di ogni sessione**: leggi `index.md` + `log.md`.
- **Alla fine di ogni sessione produttiva**: appendi una riga a `log.md` e
  aggiorna la pagina pertinente se hai scoperto un pattern nuovo.
- **Quando si scioglie una decisione aperta** (CLAUDE.md §12): sposta la voce
  risolta nella pagina `research/` giusta, con il razionale.

## Stato

Wiki appena inizializzata (bootstrap del repo). Le pagine di dominio sono seminate
dalla conoscenza minima in `CLAUDE.md` §11 e vanno arricchite con l'esperienza sul
campo (prime perizie reali, prime scansioni).
