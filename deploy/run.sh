#!/usr/bin/env bash
# Wrapper "hands-off" del giro di aste-radar (Opzione A).
# Prima di lanciare il giro: aggiorna il codice da GitHub e allinea le
# dipendenze. Così ogni modifica spinta sul ramo si applica DA SOLA al giro
# successivo, senza toccare il terminale. È fail-safe: se l'aggiornamento non
# riesce (rete/GitHub), il giro parte comunque col codice già presente.
set -uo pipefail

# Radice del repo (questo script sta in deploy/)
cd "$(cd "$(dirname "$0")/.." && pwd)"

RAMO="${ASTE_RADAR_RAMO:-claude/new-session-cy2hhl}"

echo "[run $(date '+%F %T')] aggiorno il codice (ramo $RAMO)..."
git pull -q origin "$RAMO" || echo "[run] git pull non riuscito: proseguo col codice attuale"

echo "[run] allineo le dipendenze..."
./.venv/bin/pip install -q -r requirements.txt || echo "[run] pip install non riuscito: proseguo"

echo "[run] avvio il giro..."
exec ./.venv/bin/python -m src.main
