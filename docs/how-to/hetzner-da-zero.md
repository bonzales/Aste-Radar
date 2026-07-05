# Hetzner da zero — mettere aste-radar sul server (per non tecnici)

Questa guida presuppone **zero conoscenze di server**. Obiettivo: entrare nel tuo
VPS Hetzner e far partire aste-radar. Se il **bot Kraken** gira già su quel server,
usi già un modo per entrarci: puoi saltare al punto 3 usando lo stesso accesso.

> Consiglio: fai questi passi **dal computer**, non dal telefono.

---

## 1. Cos'è e perché serve

Il tuo programma, per lavorare da solo ogni mattina, deve stare su un computer
**sempre acceso**. Quel computer è il **VPS**: un piccolo server che affitti da
Hetzner (ce l'hai già per il bot Kraken). Entriamo dentro e ci installiamo
aste-radar.

## 2. Entrare nel server (il modo più semplice: console web Hetzner)

Non serve installare niente sul tuo computer.

1. Vai su **https://console.hetzner.cloud** e accedi col tuo account Hetzner.
2. Apri il tuo **progetto**, poi la sezione **Servers**: vedrai il server (quello
   del bot Kraken). Cliccaci sopra.
3. In alto a destra clicca **`>_ Console`**: si apre una **finestra nera** (il
   "terminale") già dentro il server. È lì che si scrivono i comandi.
4. Se ti chiede un login: l'utente è di solito **`root`** e la password è quella
   che hai impostato/ricevuto quando hai creato il server. (Se non la ricordi,
   dal pannello Hetzner puoi fare **Rescue → Reset root password**.)

> Alternativa per chi sa usarlo: dal proprio computer `ssh root@<IP-del-server>`
> (l'IP è scritto nella pagina del server su Hetzner).

## 3. Installare aste-radar (copia-incolla nel terminale nero)

Incolla questi blocchi **uno alla volta** (Invio dopo ognuno). Se un comando
chiede conferma, rispondi `y` (sì).

**a) Strumenti di base** (se mancano):
```bash
apt update && apt install -y git python3.12 python3.12-venv poppler-utils tesseract-ocr tesseract-ocr-ita
```

**b) Scaricare il progetto:**
```bash
cd ~
git clone https://github.com/bonzales/Aste-Radar.git aste-radar
cd aste-radar
```

**c) Preparare Python:**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**d) Inserire i segreti del bot Telegram:**
```bash
cp config/secrets.env.example config/secrets.env
nano config/secrets.env
```
Si apre un editor: scrivi i tuoi valori dopo il `=`
```
TELEGRAM_BOT_TOKEN=8299627842:....
TELEGRAM_CHAT_ID=1288729394
```
Salva con **Ctrl+O** poi Invio, esci con **Ctrl+X**.

## 4. Prova che funzioni (una volta, a mano)

```bash
mkdir -p logs
python -m src.main
```
Se tutto va bene vedi una riga tipo `[aste-radar] trovati=.. nuovi=.. notificati=..`
e ti arrivano i lotti su Telegram. (Al primo avvio arriva l'arretrato: normale.)

## 5. Accendere la "sveglia" (sabato 07:00)

```bash
crontab -e
```
(Se chiede quale editor, scegli `nano` — il numero accanto.) In fondo incolla:
```
0 7 * * 6 cd /root/aste-radar && /root/aste-radar/.venv/bin/python -m src.main >> /root/aste-radar/logs/aste.log 2>&1
```
Salva (**Ctrl+O**, Invio) ed esci (**Ctrl+X**). Fatto: da sabato mattina
aste-radar lavora da solo. (Il PRIMO giro recupera l'arretrato degli ultimi ~6
mesi di aste ancora aperte; i giri dopo guardano solo le novità della settimana.)

## 6. Se qualcosa non torna

- Rivedi l'ultimo giro: `tail -n 30 ~/aste-radar/logs/aste.log`
- Il programma è fatto per **avvisarti su Telegram** se una scansione fallisce.
- Se ti blocchi in un passaggio, incolla qui il messaggio d'errore che vedi:
  ti dico esattamente cosa scrivere.

> Nota: i comandi assumono utente `root` (cartella `/root/...`). Se il tuo server
> usa un altro utente, sostituisci `/root/` con `/home/<tuo-utente>/`.
