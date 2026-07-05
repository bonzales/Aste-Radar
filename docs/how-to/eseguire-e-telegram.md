# Come far girare aste-radar (Fase 1) e configurare Telegram

Guida pratica per lanciare la scansione e ricevere le notifiche.

## 1. Crea il bot Telegram dedicato

1. Su Telegram apri **@BotFather** → `/newbot` → segui le istruzioni.
   Ottieni un **token** tipo `123456789:AA...`.
2. Trova il tuo **chat_id**: scrivi un messaggio al bot, poi apri nel browser
   `https://api.telegram.org/bot<TOKEN>/getUpdates` e leggi `chat.id`.
   (In alternativa usa @userinfobot.)

## 2. Metti i segreti in config/secrets.env

```bash
cp config/secrets.env.example config/secrets.env
```
Poi compila (il file è in .gitignore, NON finisce mai in git):
```
TELEGRAM_BOT_TOKEN=123456789:AA...
TELEGRAM_CHAT_ID=12345678
```

## 3. Installa le dipendenze e lancia

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m src.main
```

Output tipico:
```
[aste-radar] trovati=7 nuovi=7 notificati=7
```
- **trovati**: lotti nell'area target (provincia VE + comune di Treviso + comuni
  TV limitrofi), residenziali, pubblicati negli ultimi giorni.
- **nuovi**: mai visti prima (salvati ora in `db/aste.sqlite`).
- **notificati**: inviati su Telegram in questo giro.

Rilanciare lo stesso giorno è sicuro: **non ri-notifica** i lotti già inviati
(idempotenza). Se qualcosa va storto ricevi su Telegram `⚠️ Scansione aste
fallita: <motivo>` e il comando esce con codice ≠ 0 (fail loud).

> Primo avvio: con l'orizzonte di default (7 giorni) potresti ricevere diversi
> lotti insieme (tutto l'arretrato della settimana). È normale. Dai giorni
> successivi arriveranno solo i nuovi.

## 4. Cron giornaliero (VPS, ore 07:00)

```cron
0 7 * * * cd /percorso/aste-radar && /percorso/.venv/bin/python -m src.main >> logs/aste.log 2>&1
```

## Parametri utili (per ora nel codice, poi in config)

- `GIORNI_INDIETRO` in `src/main.py`: quanti giorni indietro guardare (default 7).
- Comuni target: `config/comuni.yaml`. Vedi
  [come aggiungere un comune](./aggiungere-un-comune.md) *(in arrivo)*.
