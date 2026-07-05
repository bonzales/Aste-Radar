"""Test del layer DB: idempotenza dell'ingest e stato di notifica (CLAUDE.md §3).

Il requisito che questi test presidiano: rilanciare lo scraper lo stesso giorno
NON deve produrre doppioni né re-notificare lotti già inviati.
"""

import sqlite3

import pytest

from src import db
from src.models import Lotto


def _lotto(id_esterno="PVP-123", fonte="pvp", prezzo_base=100000.0):
    return Lotto(
        fonte=fonte,
        id_esterno=id_esterno,
        url=f"https://pvp.giustizia.it/pvp/it/dettaglio/{id_esterno}",
        comune="Mestre",
        provincia="VE",
        titolo="Appartamento in vendita",
        prezzo_base=prezzo_base,
        data_vendita="2026-09-01",
        raw_path=f"raw/2026-07-05/{id_esterno}/index.html",
    )


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_db(c)
    yield c
    c.close()


def test_connect_su_file_imposta_row_factory_e_persiste(tmp_path):
    percorso = str(tmp_path / "aste.sqlite")
    c = db.connect(percorso)
    db.init_db(c)
    assert db.upsert_lotto(c, _lotto(id_esterno="P1"), now="t0") is True
    c.close()
    # riaprendo il file il lotto è ancora lì e i lettori funzionano (row_factory ok)
    c2 = db.connect(percorso)
    assert db.lotti_da_analizzare(c2)[0].id_esterno == "P1"
    c2.close()


def test_init_db_crea_tabella_lotti(conn):
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='lotti'"
    )
    assert cur.fetchone() is not None


def test_upsert_nuovo_lotto_inserisce_e_marca_prima_vista(conn):
    inserito = db.upsert_lotto(conn, _lotto(), now="2026-07-05T07:00:00")
    assert inserito is True
    righe = conn.execute("SELECT * FROM lotti").fetchall()
    assert len(righe) == 1
    riga = righe[0]
    assert riga["fonte"] == "pvp"
    assert riga["id_esterno"] == "PVP-123"
    assert riga["prima_vista_il"] == "2026-07-05T07:00:00"
    assert riga["notificato_il"] is None


def test_upsert_stesso_lotto_non_duplica_ne_tocca_prima_vista(conn):
    db.upsert_lotto(conn, _lotto(), now="2026-07-05T07:00:00")
    # stesso (fonte, id_esterno) rivisto il giorno dopo
    inserito = db.upsert_lotto(conn, _lotto(), now="2026-07-06T07:00:00")
    assert inserito is False
    righe = conn.execute("SELECT * FROM lotti").fetchall()
    assert len(righe) == 1
    # la prima_vista NON cambia: resta il primo avvistamento
    assert righe[0]["prima_vista_il"] == "2026-07-05T07:00:00"


def test_fonte_diversa_stesso_id_esterno_sono_lotti_distinti(conn):
    db.upsert_lotto(conn, _lotto(fonte="pvp", id_esterno="X1"), now="t0")
    db.upsert_lotto(conn, _lotto(fonte="astalegale", id_esterno="X1"), now="t0")
    assert conn.execute("SELECT COUNT(*) FROM lotti").fetchone()[0] == 2


def _id_riga(conn, id_esterno):
    return conn.execute("SELECT id FROM lotti WHERE id_esterno=?", (id_esterno,)).fetchone()["id"]


def test_da_analizzare_e_segna_analizzato():
    c = sqlite3.connect(":memory:"); c.row_factory = sqlite3.Row; db.init_db(c)
    db.upsert_lotto(c, _lotto(id_esterno="A"), now="t0")
    assert {l.id_esterno for l in db.lotti_da_analizzare(c)} == {"A"}
    db.segna_analizzato(c, _id_riga(c, "A"), now="t1", codice=1, punteggio=0.7, motivazione="ok")
    # analizzato → non torna nella coda di analisi
    assert db.lotti_da_analizzare(c) == []
    c.close()


def test_notificare_promossi_e_verifica_non_scartati(conn):
    for e in ("PASS", "VERIF", "SCART"):
        db.upsert_lotto(conn, _lotto(id_esterno=e), now="t0")
    # non ancora analizzati → coda notifica vuota (§5: si notifica solo dopo analisi)
    assert db.lotti_da_notificare(conn) == []
    db.segna_analizzato(conn, _id_riga(conn, "PASS"), "t1", codice=1, punteggio=0.9, motivazione="ottimo")
    db.segna_analizzato(conn, _id_riga(conn, "VERIF"), "t1", codice=2, punteggio=None, motivazione="manca X")
    db.segna_analizzato(conn, _id_riga(conn, "SCART"), "t1", codice=0, punteggio=None, motivazione="SCARTO")
    da_notificare = db.lotti_da_notificare(conn)
    # promosso prima, poi il 'da verificare'; lo scartato resta silenzioso
    assert [l.id_esterno for l in da_notificare] == ["PASS", "VERIF"]
    assert da_notificare[0].esito_stato == "passa"
    assert da_notificare[1].esito_stato == "verifica"


def test_segna_notificato_rimuove_dalla_coda_ed_e_idempotente(conn):
    db.upsert_lotto(conn, _lotto(id_esterno="A"), now="t0")
    db.segna_analizzato(conn, _id_riga(conn, "A"), "t1", codice=1, punteggio=0.5, motivazione="ok")
    lotto = db.lotti_da_notificare(conn)[0]
    db.segna_notificato(conn, lotto.id, now="2026-07-05T07:05:00")
    assert db.lotti_da_notificare(conn) == []
    # marcare due volte non deve rompere nulla né cambiare il timestamp
    db.segna_notificato(conn, lotto.id, now="2026-07-05T09:00:00")
    riga = conn.execute("SELECT notificato_il FROM lotti WHERE id=?", (lotto.id,)).fetchone()
    assert riga["notificato_il"] == "2026-07-05T07:05:00"
