# Accendere il bot Telegram a comandi (telecomando dal telefono)

Con questo il bot **ascolta** i tuoi comandi su Telegram, oltre a inviarti le
notifiche. Serve un piccolo servizio **sempre attivo** sul server (accanto al
cron del sabato). Gira nella cartella di aste-radar, non tocca il bot Kraken.

> Il bot risponde **solo al tuo chat** (il `TELEGRAM_CHAT_ID` nei segreti):
> chiunque altro scriva al bot viene ignorato.

## Comandi

| Comando | Cosa fa |
|---|---|
| `/status` | quanti lotti in memoria e il loro esito (promossi / da verificare / scartati) |
| `/lotto <id>` | dettaglio di un lotto già visto, es. `/lotto 4575509` |
| `/soglie` | mostra la griglia di screening attuale |
| `/scan` | lancia **subito** una scansione; i lotti promossi arrivano come notifiche |
| `/help` | l'elenco dei comandi |

Le soglie della griglia si **cambiano** scrivendo a Claude Code (non da Telegram):
la modifica al config si applica da sola al giro successivo.

## Installazione (una volta sola, sul server)

```bash
# 1) copia il servizio (adatta il percorso se non usi /root/aste-radar)
cp /root/aste-radar/deploy/aste-radar-bot.service /etc/systemd/system/

# 2) attivalo e avvialo
systemctl daemon-reload
systemctl enable --now aste-radar-bot

# 3) controlla che sia attivo
systemctl status aste-radar-bot --no-pager
```

Da ora il bot è sempre in ascolto e riparte da solo se il server si riavvia.

## Comandi utili

```bash
systemctl restart aste-radar-bot          # riavvia (es. dopo aver cambiato i segreti)
systemctl stop aste-radar-bot             # ferma il bot
journalctl -u aste-radar-bot -n 30 --no-pager   # ultimi log del bot
```

> Nota: se cambi il codice del bot, con l'Opzione A (auto-aggiornamento) il
> **cron** prende il codice nuovo al giro del sabato, ma il **servizio del bot**
> resta sul codice vecchio finché non fai `systemctl restart aste-radar-bot`.
