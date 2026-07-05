# aste-radar

Radar personale sulle **aste immobiliari giudiziarie** nel distretto di Venezia.
Ogni giorno scansiona i nuovi lotti nei comuni target, scarica le perizie,
estrae i dati chiave, li valuta con una griglia di screening e notifica su
Telegram solo i lotti che superano la soglia.

> Strumento **personale**, non un servizio pubblico né un redistributore di dati.
> Vedi [`CLAUDE.md`](./CLAUDE.md) §0 per lo scopo e i limiti.

## Documentazione

- **Per l'umano** → [`docs/`](./docs/) (organizzata secondo [Diátaxis](https://diataxis.fr/)):
  - `tutorials/` — il primo giro di scansione
  - `how-to/` — aggiungere un comune, cambiare una soglia
  - `reference/` — comandi, schema DB, formato JSON estratto
  - `explanation/` — perché questa architettura
- **Per l'agente** → [`CLAUDE.md`](./CLAUDE.md) (schema operativo) + [`research/`](./research/) (wiki di dominio)

## Struttura

```
config/     comuni.yaml, scoring.yaml, secrets.env (git-ignored)
raw/        IMMUTABILE: PDF perizie, HTML lotti (git-ignored)
db/         aste.sqlite — stato: lotti, punteggi, storico notifiche
src/        scraper → downloader → parser → extractor → scorer → notifier → main
research/   wiki di dominio persistente (Karpathy LLM-Wiki)
docs/       documentazione umana (Diátaxis)
tests/      test su perizie campione
```

## Stato del progetto

Fase 1 (MVP notifica grezza) — **in setup**. Vedi `CLAUDE.md` §4 per la roadmap a
fasi e §12 per le decisioni ancora aperte. Il log di sviluppo greppabile è in
[`research/log.md`](./research/log.md).

## Quickstart

```bash
# 1. Ambiente
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # (arriverà con la Fase 1)

# 2. Segreti — copia il template e compila
cp config/secrets.env.example config/secrets.env
$EDITOR config/secrets.env                # token Telegram, API key Anthropic

# 3. Comuni target e soglie
$EDITOR config/comuni.yaml                # comuni + tribunale competente
$EDITOR config/scoring.yaml               # pesi e soglie della griglia

# 4. Run (arriverà con la Fase 1)
# python -m src.main
```

## Stack

Python 3.12 · httpx + BeautifulSoup/lxml · poppler + Tesseract (OCR) ·
API Anthropic (estrazione) · SQLite · python-telegram-bot · cron.
Dettagli in `CLAUDE.md` §7.
