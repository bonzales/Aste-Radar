"""Re-invio dell'attuale rosa di lotti interessanti (promossi + da verificare).

A differenza del giro normale, NON ri-analizza e NON guarda `notificato_il`:
rimanda su Telegram TUTTI i lotti con esito 1/2 già in memoria. Serve, per
esempio, quando si aggiunge un nuovo destinatario e lo si vuole allineare sulla
situazione attuale. Idempotente rispetto ai dati (solo letture + invii).

Uso: python -m src.rinvia
"""

from __future__ import annotations

import sys

from src import db
from src.notifier import TelegramNotifier, leggi_secrets

DB_PATH = "db/aste.sqlite"


def reinvia_tutti(conn, notifier) -> int:
    """Re-invia ogni lotto interessante presente in memoria. Ritorna quanti."""
    lotti = db.lotti_promettenti(conn)
    for lotto in lotti:
        notifier.invia_lotto(lotto)
    return len(lotti)


def main() -> int:
    notifier = None
    try:
        secrets = leggi_secrets()
        notifier = TelegramNotifier.da_secrets(secrets)
        conn = db.connect(DB_PATH)
        db.init_db(conn)
        n = reinvia_tutti(conn, notifier)
        conn.close()
        print(f"[aste-radar] re-inviati {n} lotti interessanti (promossi + da verificare)")
        return 0
    except Exception as exc:  # fail loud (CLAUDE.md §1.4)
        motivo = f"{type(exc).__name__}: {exc}"
        print(f"[aste-radar] ERRORE re-invio: {motivo}", file=sys.stderr)
        if notifier is not None:
            try:
                notifier.invia_errore(motivo)
            except Exception:
                pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
