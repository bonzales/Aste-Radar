"""Orchestratore del ciclo giornaliero di Fase 1 (CLAUDE.md §3, §4).

ingest (scraper) -> persist idempotente (db) -> notify (telegram). Nessuna analisi.
Idempotente: rilanciare non duplica né re-notifica. Fail loud: su errore avvisa
su Telegram ed esce con codice != 0 (per cron/log).

Uso: python -m src.main
"""

from __future__ import annotations

import sys
from datetime import datetime

from src import db
from src.config import carica_target
from src.notifier import TelegramNotifier, leggi_secrets
from src.scraper import PvpClient, scansiona

DB_PATH = "db/aste.sqlite"
GIORNI_INDIETRO = 7


def esegui(client, notifier, conn, target, giorni_indietro=GIORNI_INDIETRO, now=None):
    """Nucleo testabile del run. Ritorna le statistiche del giro.

    Idempotenza: `upsert_lotto` non re-inserisce i lotti già visti; si notificano
    solo quelli con `notificato_il IS NULL`, marcandoli subito dopo l'invio.
    """
    now = now or datetime.now().isoformat(timespec="seconds")
    lotti = scansiona(client, target, giorni_indietro=giorni_indietro)
    nuovi = sum(1 for l in lotti if db.upsert_lotto(conn, l, now))

    notificati = 0
    for lotto in db.lotti_da_notificare(conn):
        notifier.invia_lotto(lotto)
        db.segna_notificato(conn, lotto.id, now)
        notificati += 1

    return {"trovati": len(lotti), "nuovi": nuovi, "notificati": notificati}


def main() -> int:
    notifier = None
    try:
        secrets = leggi_secrets()
        target = carica_target()
        notifier = TelegramNotifier.da_secrets(secrets)

        conn = db.connect(DB_PATH)
        db.init_db(conn)

        client = PvpClient()
        client.scopri_config()

        stats = esegui(client, notifier, conn, target)
        client.close()
        conn.close()
        print(
            f"[aste-radar] trovati={stats['trovati']} nuovi={stats['nuovi']} "
            f"notificati={stats['notificati']}"
        )
        return 0
    except Exception as exc:  # fail loud (CLAUDE.md §1.4)
        motivo = f"{type(exc).__name__}: {exc}"
        print(f"[aste-radar] ERRORE: {motivo}", file=sys.stderr)
        if notifier is not None:
            try:
                notifier.invia_errore(motivo)
            except Exception as exc2:
                print(f"[aste-radar] impossibile avvisare su Telegram: {exc2}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
