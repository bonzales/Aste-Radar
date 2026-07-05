# Come mettere aste-radar in produzione sul VPS (funzionamento autonomo)

Obiettivo: far girare aste-radar **ogni giorno alle 07:00 da solo** sul VPS
Hetzner (Ubuntu 24.04, Python 3.12), lo stesso del bot Kraken.

> Tutti i comandi si eseguono **sul VPS** (via SSH), non in questo ambiente.
> Sostituisci `<...>` con i tuoi valori.

## 1. Prendi il codice sul VPS

```bash
cd ~
git clone <url-del-repo> aste-radar     # oppure: git pull, se già clonato
cd aste-radar
git checkout claude/new-session-cy2hhl  # oppure 'main' se il ramo è già stato unito
```

## 2. Ambiente Python e dipendenze

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3. Segreti (token del bot dedicato)

```bash
cp config/secrets.env.example config/secrets.env
nano config/secrets.env
```
Compila:
```
TELEGRAM_BOT_TOKEN=<il tuo token>
TELEGRAM_CHAT_ID=<il tuo chat_id>
```
(`config/secrets.env` è in .gitignore: resta solo sul server, non va su GitHub.)

## 4. Prova manuale (prima di automatizzare)

```bash
mkdir -p logs
python -m src.main
```
Atteso: `[aste-radar] trovati=.. nuovi=.. notificati=..` e le notifiche su
Telegram. Al **primo avvio** arriva l'arretrato degli ultimi 7 giorni: normale.
Se qualcosa va storto ricevi `⚠️ Scansione aste fallita: <motivo>` (fail loud).

## 5. La sveglia: cron SETTIMANALE (sabato 07:00)

```bash
crontab -e
```
Aggiungi questa riga (aggiusta i percorsi):
```cron
0 7 * * 6 cd /home/<utente>/aste-radar && /home/<utente>/aste-radar/.venv/bin/python -m src.main >> /home/<utente>/aste-radar/logs/aste.log 2>&1
```
Da qui in poi aste-radar lavora da solo: ogni SABATO controlla i nuovi lotti e
ti scrive su Telegram solo quelli nuovi. Rilanci lo stesso giorno non creano
doppioni (idempotenza).

## 6. Controlli utili

```bash
tail -n 30 logs/aste.log        # cosa ha fatto l'ultimo giro
sqlite3 db/aste.sqlite "SELECT COUNT(*) FROM lotti;"   # quanti lotti in memoria
```

## Note

- **Backup**: l'unico stato da conservare è `db/aste.sqlite` (la memoria dei lotti
  già visti/notificati) e `config/secrets.env`. Il resto è nel repo.
- **Orizzonte temporale**: `GIORNI_INDIETRO` in `src/main.py` (default 7). Il cron
  giornaliero copre ampiamente; alzalo solo se salti dei giorni.
- **Aggiornamenti**: `git pull` e riavvio non serve — il prossimo cron userà il
  codice nuovo.
- **Alternativa a cron**: un timer `systemd` dà log e ripartenze più robuste; il
  cron è sufficiente per iniziare (coerente con CLAUDE.md §7).
