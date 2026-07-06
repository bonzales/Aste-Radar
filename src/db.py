"""Layer DB (SQLite) — stato dei lotti e idempotenza (CLAUDE.md §3).

Garanzie presidiate dai test in tests/test_db.py:
- rilanciare l'ingest non duplica i lotti (chiave logica: fonte + id_esterno);
- il primo avvistamento (`prima_vista_il`) non viene mai sovrascritto;
- un lotto già notificato non torna nella coda di notifica.

Il modulo lavora su una connessione sqlite3 passata dall'esterno, così i test
possono usare `:memory:` e il resto della pipeline un file su disco.
"""

from __future__ import annotations

import sqlite3

from src.models import Lotto

# Colonne selezionate quando ricostruiamo un Lotto dal DB.
_COLS = (
    "id, fonte, id_esterno, url, comune, provincia, titolo, prezzo_base, "
    "data_vendita, raw_path, prima_vista_il, notificato_il, "
    "analizzato_il, esito_passa, punteggio, motivazione"
)

# Colonne aggiunte in Fase 3 (analisi): un lotto si analizza UNA volta sola
# (download+OCR+IA costano), poi si conserva l'esito.
_COLONNE_ANALISI = {
    "analizzato_il": "TEXT",
    "esito_passa": "INTEGER",
    "punteggio": "REAL",
    "motivazione": "TEXT",
}


def connect(path: str) -> sqlite3.Connection:
    """Apre (o crea) il DB con `row_factory` impostato: invariante richiesto dai
    lettori di questo modulo. Usare questa funzione al posto di sqlite3.connect
    diretto, così main.py non può dimenticare la row_factory."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Crea lo schema minimo di Fase 1 se non esiste già (idempotente)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS lotti (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            fonte          TEXT NOT NULL,
            id_esterno     TEXT NOT NULL,
            url            TEXT,
            comune         TEXT,
            provincia      TEXT,
            titolo         TEXT,
            prezzo_base    REAL,
            data_vendita   TEXT,
            raw_path       TEXT,
            prima_vista_il TEXT NOT NULL,
            notificato_il  TEXT,
            analizzato_il  TEXT,
            esito_passa    INTEGER,
            punteggio      REAL,
            motivazione    TEXT,
            UNIQUE (fonte, id_esterno)
        )
        """
    )
    _assicura_colonne(conn)
    conn.commit()


def _assicura_colonne(conn: sqlite3.Connection) -> None:
    """Aggiunge le colonne di analisi a un DB preesistente (migrazione leggera)."""
    esistenti = {r["name"] for r in conn.execute("PRAGMA table_info(lotti)")}
    for nome, tipo in _COLONNE_ANALISI.items():
        if nome not in esistenti:
            conn.execute(f"ALTER TABLE lotti ADD COLUMN {nome} {tipo}")


def upsert_lotto(conn: sqlite3.Connection, lotto: Lotto, now: str) -> bool:
    """Inserisce il lotto se nuovo. Ritorna True se inserito, False se già visto.

    Su un lotto già presente (stessa coppia fonte+id_esterno) è un no-op: NON
    duplica, NON tocca `prima_vista_il` né lo stato di notifica. In Fase 1 non
    aggiorniamo i campi volatili (es. ribassi di prezzo): è materia di fasi dopo.
    """
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO lotti
            (fonte, id_esterno, url, comune, provincia, titolo,
             prezzo_base, data_vendita, raw_path, prima_vista_il, notificato_il)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        (
            lotto.fonte,
            lotto.id_esterno,
            lotto.url,
            lotto.comune,
            lotto.provincia,
            lotto.titolo,
            lotto.prezzo_base,
            lotto.data_vendita,
            lotto.raw_path,
            now,
        ),
    )
    conn.commit()
    # rowcount == 1 solo se l'INSERT ha effettivamente inserito (non IGNORE).
    return cur.rowcount == 1


def lotti_da_analizzare(conn: sqlite3.Connection) -> list[Lotto]:
    """Lotti target non ancora analizzati (Livello 2): download+OCR+IA una volta sola."""
    rows = conn.execute(
        f"SELECT {_COLS} FROM lotti WHERE analizzato_il IS NULL "
        f"ORDER BY prima_vista_il, id"
    ).fetchall()
    return [_row_to_lotto(r) for r in rows]


def segna_analizzato(
    conn: sqlite3.Connection,
    lotto_id: int,
    now: str,
    codice: int,
    punteggio: float | None,
    motivazione: str | None,
) -> None:
    """Registra l'esito dell'analisi (codice: 1=passa, 2=verifica, 0=scarta).
    Idempotente: non ri-analizza (AND analizzato_il IS NULL)."""
    conn.execute(
        "UPDATE lotti SET analizzato_il=?, esito_passa=?, punteggio=?, motivazione=? "
        "WHERE id=? AND analizzato_il IS NULL",
        (now, codice, punteggio, motivazione, lotto_id),
    )
    conn.commit()


def lotti_da_notificare(conn: sqlite3.Connection) -> list[Lotto]:
    """Lotti da notificare non ancora inviati: i promossi (1) e i 'da verificare'
    (2, promettenti ma con dati mancanti — per non perdere opportunità). Gli
    scartati (0) restano silenziosi (§5). Prima i promossi, poi per punteggio."""
    rows = conn.execute(
        f"SELECT {_COLS} FROM lotti "
        f"WHERE notificato_il IS NULL AND esito_passa IN (1, 2) "
        f"ORDER BY esito_passa ASC, punteggio DESC, prima_vista_il"
    ).fetchall()
    return [_row_to_lotto(r) for r in rows]


def lotti_promettenti(conn: sqlite3.Connection) -> list[Lotto]:
    """TUTTI i lotti interessanti (promossi=1 e da verificare=2), a prescindere da
    quando/se sono già stati notificati. Serve per re-inviare l'attuale rosa (es.
    quando si aggiunge un nuovo destinatario). Stesso ordine di lotti_da_notificare."""
    rows = conn.execute(
        f"SELECT {_COLS} FROM lotti "
        f"WHERE esito_passa IN (1, 2) "
        f"ORDER BY esito_passa ASC, punteggio DESC, prima_vista_il"
    ).fetchall()
    return [_row_to_lotto(r) for r in rows]


def segna_notificato(conn: sqlite3.Connection, lotto_id: int, now: str) -> None:
    """Marca il lotto come notificato. Idempotente: se già marcato, non tocca il
    timestamp esistente (la clausola AND notificato_il IS NULL protegge)."""
    conn.execute(
        "UPDATE lotti SET notificato_il = ? WHERE id = ? AND notificato_il IS NULL",
        (now, lotto_id),
    )
    conn.commit()


def _row_to_lotto(row: sqlite3.Row) -> Lotto:
    return Lotto(
        id=row["id"],
        fonte=row["fonte"],
        id_esterno=row["id_esterno"],
        url=row["url"],
        comune=row["comune"],
        provincia=row["provincia"],
        titolo=row["titolo"],
        prezzo_base=row["prezzo_base"],
        data_vendita=row["data_vendita"],
        raw_path=row["raw_path"],
        prima_vista_il=row["prima_vista_il"],
        notificato_il=row["notificato_il"],
        punteggio=row["punteggio"],
        motivazione=row["motivazione"],
        esito_stato={1: "passa", 2: "verifica", 0: "scarta"}.get(row["esito_passa"]),
    )
