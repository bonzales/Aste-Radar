"""Test di integrazione del funnel (esegui): scan -> analisi una-tantum -> notifica
solo i promossi, con idempotenza. L'analisi di Livello 2 (_analizza_lotto) è
stubbata: qui si presidia l'ORCHESTRAZIONE, non OCR/IA (testati altrove)."""

import sqlite3
from datetime import date, timedelta

import pytest

from src import db, main as main_mod
from src.config import TargetGeo
from src.scorer import Esito
from src.scraper import CATEGORIA_RESIDENZIALE

OGGI = date.today()
FUT = (OGGI + timedelta(days=365)).isoformat()
PUB = OGGI.isoformat()


class FakeClient:
    def __init__(self, content):
        self._content = content

    def cerca(self, page, size, sort="dataPubblicazione,desc"):
        if page == 0:
            return {"body": {"content": self._content, "last": True}}
        return {"body": {"content": [], "last": True}}


class FakeNotifier:
    def __init__(self):
        self.inviati = []

    def invia_lotto(self, lotto):
        self.inviati.append(lotto.id_esterno)


def _content():
    def lot(idv, citta, prov, cat, prezzo):
        return {"id": idv, "categoriaLotto": cat, "descLotto": f"Lotto {idv}",
                "prezzoBaseAsta": prezzo, "dataVendita": FUT, "dataPubblicazione": PUB,
                "indirizzo": {"citta": citta, "provincia": prov}}
    return [
        lot(111, "Venezia", "Venezia", CATEGORIA_RESIDENZIALE, 90000.0),   # target, passerà
        lot(222, "Mestre", "Venezia", CATEGORIA_RESIDENZIALE, 100000.0),   # target, scarterà
        lot(555, "Chioggia", "Venezia", CATEGORIA_RESIDENZIALE, 70000.0),  # target, da verificare
        lot(333, "Palermo", "Palermo", CATEGORIA_RESIDENZIALE, 80000.0),   # fuori area
        lot(444, "Venezia", "Venezia", CATEGORIA_RESIDENZIALE, 999000.0),  # oltre budget
    ]


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_db(c)
    yield c
    c.close()


def _stub_analisi(lotto, client, ai_client, griglia, dir_raw, max_pagine_ocr):
    if lotto.id_esterno == "111":   # promosso
        return Esito(passa=True, sconto=0.35, punteggio=0.8,
                     motivazioni=["prezzo 35% sotto stima", "libero", "cat. A/2"])
    if lotto.id_esterno == "555":   # promettente ma dati mancanti → verifica
        return Esito(passa=False, sconto=None, punteggio=None,
                     da_verificare=["occupazione non classificata"])
    return Esito(passa=False, sconto=0.10, punteggio=None,   # scartato hard
                 scarti=["sconto 10% sotto la soglia 25%"])


def test_funnel_notifica_promossi_e_verifica_non_scartati(conn, monkeypatch):
    monkeypatch.setattr(main_mod, "_analizza_lotto", _stub_analisi)
    target = TargetGeo(province_intere={"venezia"}, solo_residenziale=True)
    notifier = FakeNotifier()
    stats = main_mod.esegui(
        FakeClient(_content()), None, notifier, conn, target, {"hard": {}},
        giorni_indietro=14, prezzo_max=150000, now="2026-07-05T07:00:00",
    )
    # Livello 1: 111, 222, 555 target entro budget (333 fuori area, 444 oltre budget)
    assert stats["trovati"] == 3
    assert stats["analizzati"] == 3
    # 111 (passa) + 555 (da verificare) notificati; 222 (scarto hard) no
    assert stats["notificati"] == 2
    assert notifier.inviati == ["111", "555"]


def test_funnel_idempotente_secondo_giro(conn, monkeypatch):
    monkeypatch.setattr(main_mod, "_analizza_lotto", _stub_analisi)
    target = TargetGeo(province_intere={"venezia"}, solo_residenziale=True)
    main_mod.esegui(FakeClient(_content()), None, FakeNotifier(), conn, target,
                    {"hard": {}}, giorni_indietro=14, prezzo_max=150000, now="2026-07-05T07:00:00")
    # secondo giro: niente da analizzare né da notificare di nuovo
    n2 = FakeNotifier()
    stats2 = main_mod.esegui(FakeClient(_content()), None, n2, conn, target,
                             {"hard": {}}, giorni_indietro=14, prezzo_max=150000,
                             now="2026-07-12T07:00:00")
    assert stats2["analizzati"] == 0
    assert stats2["notificati"] == 0
    assert n2.inviati == []


def test_lotto_scartato_non_si_notifica_ma_resta_analizzato(conn, monkeypatch):
    monkeypatch.setattr(main_mod, "_analizza_lotto", _stub_analisi)
    target = TargetGeo(province_intere={"venezia"}, solo_residenziale=True)
    main_mod.esegui(FakeClient(_content()), None, FakeNotifier(), conn, target,
                    {"hard": {}}, giorni_indietro=14, prezzo_max=150000, now="2026-07-05T07:00:00")
    riga = conn.execute("SELECT esito_passa, motivazione FROM lotti WHERE id_esterno='222'").fetchone()
    assert riga["esito_passa"] == 0
    assert "SCARTO" in riga["motivazione"]
