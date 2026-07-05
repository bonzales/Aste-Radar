#!/usr/bin/env bash
# Setup one-shot di aste-radar sul VPS (CLAUDE.md §7).
# Installa strumenti, ambiente Python, chiede i segreti, installa il cron del
# sabato e (opzionale) lancia subito il primo giro completo in background.
# NON tocca altri programmi sul server (vive nella sua cartella + venv).
set -euo pipefail

# Vai alla radice del repo (questo script sta in deploy/)
cd "$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(pwd)"

echo "== aste-radar — setup =="
echo

echo "[1/5] Installo gli strumenti di sistema (git, python, OCR)..."
apt-get update -q
apt-get install -y -q git python3.12 python3.12-venv poppler-utils tesseract-ocr tesseract-ocr-ita

echo "[2/5] Creo l'ambiente Python e installo le dipendenze..."
python3.12 -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -r requirements.txt

echo "[3/5] Segreti (incolla i valori quando richiesto)."
[ -f config/secrets.env ] || cp config/secrets.env.example config/secrets.env
read -r -p "  Token del bot Telegram: " TG_TOKEN
read -r -p "  Chat ID Telegram: " TG_CHAT
read -r -p "  Chiave API Anthropic (sk-ant-...): " AI_KEY
TG_TOKEN="$TG_TOKEN" TG_CHAT="$TG_CHAT" AI_KEY="$AI_KEY" python3 - <<'PY'
import os, pathlib, re
p = pathlib.Path("config/secrets.env"); t = p.read_text()
t = re.sub(r'^TELEGRAM_BOT_TOKEN=.*$', 'TELEGRAM_BOT_TOKEN='+os.environ['TG_TOKEN'], t, flags=re.M)
t = re.sub(r'^TELEGRAM_CHAT_ID=.*$',   'TELEGRAM_CHAT_ID='+os.environ['TG_CHAT'],   t, flags=re.M)
t = re.sub(r'^ANTHROPIC_API_KEY=.*$',  'ANTHROPIC_API_KEY='+os.environ['AI_KEY'],   t, flags=re.M)
p.write_text(t)
print("  secrets.env scritto (resta solo sul server).")
PY

echo "[4/5] Installo la sveglia settimanale (sabato 07:00), senza toccare gli altri cron..."
CRON_LINE="0 7 * * 6 cd $REPO && $REPO/.venv/bin/python -m src.main >> $REPO/logs/aste.log 2>&1"
mkdir -p logs
( crontab -l 2>/dev/null | grep -v 'aste-radar' || true; echo "$CRON_LINE" ) | crontab -
echo "  cron installato."

echo "[5/5] Tutto pronto."
echo
read -r -p "Lancio ORA il primo giro completo in background (1-3 ore)? (s/n): " GO
if [ "$GO" = "s" ] || [ "$GO" = "S" ]; then
  nohup ./.venv/bin/python -m src.main >> logs/aste.log 2>&1 &
  echo
  echo "  ✅ Primo giro avviato. Segui l'avanzamento con:"
  echo "       tail -f $REPO/logs/aste.log"
  echo "  (esci dalla vista con Ctrl+C; il giro continua da solo.)"
else
  echo
  echo "  Quando vuoi lanciarlo:"
  echo "       cd $REPO && nohup ./.venv/bin/python -m src.main >> logs/aste.log 2>&1 &"
fi
