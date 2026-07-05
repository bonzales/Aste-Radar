"""Test di integrazione del nucleo orchestrazione (esegui): end-to-end con
fake per scraper e notifier, DB in memoria. Presidia idempotenza e fail loud a
livello di ciclo (CLAUDE.md §3)."""

import sqlite3

import pytest

from src import db
from src.config import TargetGeo
from src.main import esegui
from src.scraper import CATEGORIA_RESIDENZIALE


class FakeClient:
    """Restituisce una pagina di risultati poi si esaurisce."""

    def __init__(self, content):
        self._content = content
        self.chiamate = 0

    def cerca(self, page, size, sort="dataPubblicazione,desc"):
        self.chiamate += 1
        if page == 0:
            return {"body": {"content": self._content, "last": True}}
        return {"body": {"content": [], "last": True}}


class FakeNotifier:
    def __init__(self):
        self.inviati = []
        self.errori = []

    def invia_lotto(self, lotto):
        self.inviati.append(lotto.id_esterno)

    def invia_errore(self, motivo):
        self.errori.append(motivo)


def _content():
    return [
        {"id": 111, "categoriaLotto": CATEGORIA_RESIDENZIALE, "descLotto": "Casa a Mestre",
         "prezzoBaseAsta": 90000.0, "dataVendita": "2026-09-01",
         "dataPubblicazione": "2026-07-04",
         "indirizzo": {"citta": "Venezia", "provincia": "Venezia"}},
        {"id": 222, "categoriaLotto": "IMMOBILE_COMMERCIALE", "descLotto": "Negozio",
         "dataPubblicazione": "2026-07-04",
         "indirizzo": {"citta": "Venezia", "provincia": "Venezia"}},
        {"id": 333, "categoriaLotto": CATEGORIA_RESIDENZIALE, "descLotto": "Villa a Palermo",
         "dataPubblicazione": "2026-07-04",
         "indirizzo": {"citta": "Palermo", "provincia": "Palermo"}},
    ]


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_db(c)
    yield c
    c.close()


def test_esegui_notifica_solo_i_lotti_target(conn):
    target = TargetGeo(province_intere={"venezia"}, solo_residenziale=True)
    notifier = FakeNotifier()
    stats = esegui(FakeClient(_content()), notifier, conn, target,
                   giorni_indietro=30, now="2026-07-05T07:00:00")
    # solo il residenziale di Venezia (111): 222 commerciale, 333 Palermo esclusi
    assert stats["trovati"] == 1
    assert stats["nuovi"] == 1
    assert stats["notificati"] == 1
    assert notifier.inviati == ["111"]


def test_esegui_e_idempotente_secondo_giro_non_ri_notifica(conn):
    target = TargetGeo(province_intere={"venezia"}, solo_residenziale=True)
    n1 = FakeNotifier()
    esegui(FakeClient(_content()), n1, conn, target,
           giorni_indietro=30, now="2026-07-05T07:00:00")
    # secondo giro, stessi dati, giorno dopo
    n2 = FakeNotifier()
    stats2 = esegui(FakeClient(_content()), n2, conn, target,
                    giorni_indietro=30, now="2026-07-06T07:00:00")
    assert stats2["nuovi"] == 0
    assert stats2["notificati"] == 0
    assert n2.inviati == []
    # nessun doppione in DB
    assert conn.execute("SELECT COUNT(*) FROM lotti").fetchone()[0] == 1
