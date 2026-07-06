"""Test del re-invio della rosa attuale (promossi + da verificare), a
prescindere da `notificato_il`."""

import sqlite3

import pytest

from src import db, rinvia


class FakeNotifier:
    def __init__(self):
        self.inviati = []

    def invia_lotto(self, lotto):
        self.inviati.append(lotto.id_esterno)


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_db(c)
    # promosso GIÀ notificato, da-verificare notificato, scartato, non analizzato
    c.execute(
        "INSERT INTO lotti (fonte,id_esterno,comune,prezzo_base,prima_vista_il,"
        "notificato_il,analizzato_il,esito_passa,punteggio) "
        "VALUES ('pvp','111','Chioggia',90000,'2026-07-05','2026-07-05','2026-07-05',1,0.8)"
    )
    c.execute(
        "INSERT INTO lotti (fonte,id_esterno,comune,prezzo_base,prima_vista_il,"
        "notificato_il,analizzato_il,esito_passa) "
        "VALUES ('pvp','222','Pianiga',70000,'2026-07-05','2026-07-05','2026-07-05',2)"
    )
    c.execute(
        "INSERT INTO lotti (fonte,id_esterno,comune,prezzo_base,prima_vista_il,"
        "analizzato_il,esito_passa) VALUES ('pvp','333','Mira',100000,'2026-07-05','2026-07-05',0)"
    )
    c.execute(
        "INSERT INTO lotti (fonte,id_esterno,comune,prezzo_base,prima_vista_il) "
        "VALUES ('pvp','444','Venezia',80000,'2026-07-05')"
    )
    c.commit()
    yield c
    c.close()


def test_reinvia_manda_promossi_e_verifica_anche_se_gia_notificati(conn):
    n = FakeNotifier()
    quanti = rinvia.reinvia_tutti(conn, n)
    assert quanti == 2
    # promosso prima (esito 1), poi da-verificare (esito 2)
    assert n.inviati == ["111", "222"]


def test_reinvia_non_tocca_scartati_ne_non_analizzati(conn):
    n = FakeNotifier()
    rinvia.reinvia_tutti(conn, n)
    assert "333" not in n.inviati  # scartato
    assert "444" not in n.inviati  # non analizzato
