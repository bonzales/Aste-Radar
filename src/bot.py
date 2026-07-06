"""Bot Telegram a COMANDI (CLAUDE.md §6): il telecomando dal telefono.

In ascolto (long-polling) sul solo chat autorizzato. Solo comandi strutturati
(gratis) — niente linguaggio libero, che costerebbe una chiamata IA per messaggio
ed è "spento di default" per scelta (§6).

Comandi:
  /help              elenco comandi
  /status            quanti lotti in memoria, quanti promossi/da verificare/scartati
  /lotto <id>        dettaglio di un lotto già visto (per id del portale)
  /soglie            mostra la griglia attuale (i valori si CAMBIANO via Claude Code)
  /scan              lancia subito una scansione (i risultati arrivano come notifiche)

Sicurezza: il bot risponde SOLO al TELEGRAM_CHAT_ID dei segreti. Ogni messaggio
da altri chat viene ignorato (chiunque potrebbe scrivere al bot).

La parte deterministica (auth, dispatch, formattazione) è testata; il ciclo di
long-polling è I/O sottile (smoke), coerente con §9.2.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

from src import db
from src.scorer import carica_griglia

DB_PATH = "db/aste.sqlite"

AIUTO = (
    "🏠 aste-radar — comandi disponibili:\n"
    "/status — stato: lotti in memoria e loro esito\n"
    "/lotto <id> — dettaglio di un lotto (id del portale, es. /lotto 4575509)\n"
    "/soglie — la griglia di screening attuale\n"
    "/scan — lancia subito una scansione (i lotti promossi arrivano qui)\n"
    "/rinvia — rimanda tutti i lotti interessanti già trovati (utile dopo aver "
    "aggiunto una persona)\n"
    "/help — questo messaggio\n\n"
    "Per CAMBIARE le soglie della griglia scrivi a Claude Code: le modifiche "
    "al codice/config si applicano da sole al giro successivo."
)

STATO_ETICHETTA = {1: "✅ promosso", 2: "⚠️ da verificare", 0: "❌ scartato"}


def _euro(v) -> str:
    if v is None:
        return "—"
    return f"€ {v:,.0f}".replace(",", ".")


# --- Logica pura, testabile -------------------------------------------------

def chat_autorizzati(valore) -> set[str]:
    """Insieme dei chat id autorizzati. Ammette un id singolo o più id separati
    da virgola/punto e virgola (per condividere il bot con più persone)."""
    if valore is None:
        return set()
    if isinstance(valore, (set, list, tuple)):
        grezzi = [str(v) for v in valore]
    else:
        grezzi = str(valore).replace(";", ",").split(",")
    return {c.strip() for c in grezzi if c.strip()}


def estrai_chat_e_testo(update: dict) -> tuple[str, str] | None:
    """(chat_id, testo) del messaggio, o None se l'update non è un messaggio."""
    msg = update.get("message") or update.get("edited_message")
    if not msg:
        return None
    return str((msg.get("chat") or {}).get("id")), (msg.get("text") or "")


def messaggio_autorizzato(update: dict, autorizzati) -> str | None:
    """Ritorna il testo del messaggio SOLO se proviene da un chat autorizzato,
    altrimenti None. È il gate di sicurezza del bot."""
    estratto = estrai_chat_e_testo(update)
    if estratto is None:
        return None
    chat_id, testo = estratto
    return testo if chat_id in chat_autorizzati(autorizzati) else None


def testo_non_autorizzato(chat_id: str) -> str:
    """Risposta a un chat non autorizzato: gli comunica il suo id così il
    proprietario può aggiungerlo (è il modo per condividere il bot)."""
    return (
        "🔒 Questo chat non è autorizzato a usare il bot.\n"
        f"Id di questo chat: {chat_id}\n"
        "Per essere abilitato, chiedi al proprietario di aggiungere questo id in "
        "config/secrets.env (TELEGRAM_CHAT_ID, separato da virgola)."
    )


def _conta_stato(conn) -> dict:
    def uno(sql, *p):
        return conn.execute(sql, p).fetchone()[0]

    return {
        "totale": uno("SELECT COUNT(*) FROM lotti"),
        "da_analizzare": uno("SELECT COUNT(*) FROM lotti WHERE analizzato_il IS NULL"),
        "promossi": uno("SELECT COUNT(*) FROM lotti WHERE esito_passa=1"),
        "da_verificare": uno("SELECT COUNT(*) FROM lotti WHERE esito_passa=2"),
        "scartati": uno("SELECT COUNT(*) FROM lotti WHERE esito_passa=0"),
        "notificati": uno("SELECT COUNT(*) FROM lotti WHERE notificato_il IS NOT NULL"),
    }


def formatta_status(conn) -> str:
    s = _conta_stato(conn)
    return (
        f"📊 Stato\n"
        f"Lotti in memoria: {s['totale']}\n"
        f"Ancora da analizzare: {s['da_analizzare']}\n"
        f"✅ Promossi: {s['promossi']}\n"
        f"⚠️ Da verificare: {s['da_verificare']}\n"
        f"❌ Scartati: {s['scartati']}\n"
        f"Notificati finora: {s['notificati']}"
    )


def descrivi_lotto(conn, id_esterno: str) -> str:
    row = conn.execute(
        "SELECT * FROM lotti WHERE id_esterno = ?", (str(id_esterno),)
    ).fetchone()
    if row is None:
        return f"Nessun lotto con id {id_esterno} in memoria."
    righe = [f"🏠 {row['titolo'] or 'Lotto'} (id {row['id_esterno']})"]
    luogo = " ".join(p for p in [row["comune"], f"({row['provincia']})" if row["provincia"] else None] if p)
    if luogo:
        righe.append(f"📍 {luogo}")
    righe.append(f"💶 Base: {_euro(row['prezzo_base'])}")
    if row["data_vendita"]:
        righe.append(f"🗓 Vendita: {row['data_vendita']}")
    etichetta = STATO_ETICHETTA.get(row["esito_passa"], "— non ancora analizzato")
    righe.append(f"Esito: {etichetta}")
    if row["motivazione"]:
        righe.append(f"📝 {row['motivazione']}")
    if row["url"]:
        righe.append(f"🔗 {row['url']}")
    return "\n".join(righe)


def formatta_soglie(griglia: dict) -> str:
    hard = griglia.get("hard") or {}
    flip = griglia.get("flip") or {}

    def pct(v):
        return f"{v * 100:.0f}%" if isinstance(v, (int, float)) else "—"

    occ = ", ".join(hard.get("occupazione_ammessa") or []) or "—"
    cats = ", ".join(hard.get("categorie_ammesse") or []) or "—"
    righe = [
        "⚙️ Griglia attuale (criteri HARD)",
        f"Sconto minimo sulla stima: {pct(hard.get('sconto_min_su_stima'))}",
        f"Prezzo base massimo: {_euro(hard.get('prezzo_base_max'))}",
        f"Occupazione ammessa: {occ}",
        f"Solo piena proprietà: {'sì' if hard.get('solo_piena_proprieta') else 'no'}",
        f"Categorie: {cats}",
        f"Superficie mq: {hard.get('superficie_mq_min') or '—'} … {hard.get('superficie_mq_max') or '—'}",
    ]
    if griglia.get("calcola_margine_flip"):
        righe.append(
            "\n💰 Margine flip (indicativo): rivendita "
            f"{pct(flip.get('rivendita_su_stima'))} della stima, ristrutturazione "
            f"{_euro(flip.get('ristrutturazione_eur_mq'))}/mq"
        )
    righe.append("\nPer modificarle: scrivi a Claude Code.")
    return "\n".join(righe)


def gestisci_comando(testo: str, *, conn, griglia: dict, avvia_scan=None,
                     avvia_reinvio=None) -> str | None:
    """Traduce un messaggio in una risposta. Ritorna None se non c'è nulla da
    rispondere. Funzione pura rispetto all'I/O di rete (testabile)."""
    testo = (testo or "").strip()
    if not testo.startswith("/"):
        return "Non capisco il linguaggio libero (per ora). Scrivi /help per i comandi."

    parti = testo.split()
    comando = parti[0].lstrip("/").split("@")[0].lower()
    args = parti[1:]

    if comando in ("help", "start"):
        return AIUTO
    if comando == "status":
        return formatta_status(conn)
    if comando == "soglie":
        return formatta_soglie(griglia)
    if comando == "lotto":
        if not args:
            return "Uso: /lotto <id> (es. /lotto 4575509)"
        return descrivi_lotto(conn, args[0])
    if comando == "scan":
        if avvia_scan is None:
            return "Scansione non disponibile."
        avvia_scan()
        return "🔍 Scansione avviata. Ti avviso qui con i lotti promossi (può volerci qualche minuto)."
    if comando == "rinvia":
        if avvia_reinvio is None:
            return "Re-invio non disponibile."
        avvia_reinvio()
        return "📤 Re-invio della rosa attuale avviato: i lotti interessanti arrivano a tutti i destinatari."
    return f"Comando sconosciuto: /{comando}. Scrivi /help."


# --- I/O: long-polling (sottile) -------------------------------------------

def _get_updates(http: httpx.Client, token: str, offset: int | None) -> list[dict]:
    resp = http.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={"timeout": 60, "offset": offset} if offset else {"timeout": 60},
    )
    resp.raise_for_status()
    return resp.json().get("result", [])


def _invia(http: httpx.Client, token: str, chat_id: str, testo: str) -> None:
    http.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": testo, "disable_web_page_preview": True},
    )


def esegui_bot() -> None:
    from src.notifier import leggi_secrets

    secrets = leggi_secrets()
    token = secrets.get("TELEGRAM_BOT_TOKEN")
    autorizzati = chat_autorizzati(secrets.get("TELEGRAM_CHAT_ID"))
    if not token or not autorizzati:
        raise RuntimeError("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID mancanti in config/secrets.env")

    conn = db.connect(DB_PATH)
    db.init_db(conn)

    def avvia_scan() -> None:
        # sottoprocesso isolato: riusa tutta la pipeline e notifica i risultati da
        # sé; evita problemi di concorrenza SQLite tra thread.
        subprocess.Popen([sys.executable, "-m", "src.main"], cwd=os.getcwd())

    def avvia_reinvio() -> None:
        subprocess.Popen([sys.executable, "-m", "src.rinvia"], cwd=os.getcwd())

    http = httpx.Client(timeout=70.0)
    offset: int | None = None
    print("[aste-radar bot] in ascolto...", flush=True)
    while True:
        try:
            updates = _get_updates(http, token, offset)
        except Exception as exc:  # rete instabile: non morire, riprova
            print(f"[aste-radar bot] getUpdates fallito: {exc}", file=sys.stderr, flush=True)
            time.sleep(5)
            continue
        for u in updates:
            offset = u["update_id"] + 1
            estratto = estrai_chat_e_testo(u)
            if estratto is None:
                continue
            chat_id, testo = estratto
            if chat_id not in autorizzati:
                # non autorizzato: gli diciamo il suo id così può essere aggiunto
                risposta = testo_non_autorizzato(chat_id)
            else:
                try:
                    # griglia riletta a ogni comando: riflette i cambi di config
                    griglia = carica_griglia()
                    risposta = gestisci_comando(testo, conn=conn, griglia=griglia,
                                                avvia_scan=avvia_scan, avvia_reinvio=avvia_reinvio)
                except Exception as exc:
                    risposta = f"⚠️ Errore nell'eseguire il comando: {exc}"
            if risposta:
                try:
                    _invia(http, token, chat_id, risposta)
                except Exception as exc:
                    print(f"[aste-radar bot] invio fallito: {exc}", file=sys.stderr, flush=True)


if __name__ == "__main__":
    esegui_bot()
