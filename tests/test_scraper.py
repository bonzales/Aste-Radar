"""Test della logica deterministica dello scraper: mapping e filtro geografico.

L'I/O HTTP (PvpClient) non è testato qui in TDD (§9.2: I/O volatile → integrazione).
Le fixture sono risposte reali del PVP salvate in tests/fixtures/pvp/.
"""

import json
from pathlib import Path

from src.config import TargetGeo
from src.models import Lotto
from src.scraper import (
    CATEGORIA_RESIDENZIALE,
    filtra_lotti,
    parse_risposta_ricerca,
)

FIXTURE = Path("tests/fixtures/pvp/ricerca-mestre.json")


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_mappa_i_campi_dalla_risposta_reale():
    lotti = parse_risposta_ricerca(_fixture())
    assert len(lotti) == 3
    # tutti hanno id_esterno e url di dettaglio col giusto parametro
    assert all(l.fonte == "pvp" and l.id_esterno for l in lotti)
    assert all("detail_annuncio.page?idAnnuncio=" in l.url for l in lotti)
    # il residenziale di Venezia è mappato correttamente
    res = next(l for l in lotti if l.categoria == CATEGORIA_RESIDENZIALE)
    assert res.provincia == "Venezia"
    assert res.comune == "Venezia"
    assert res.prezzo_base == 10000.0
    assert res.data_pubblicazione == "2026-03-16"


def test_parse_scarta_item_senza_id():
    data = {"body": {"content": [{"descLotto": "senza id"}, {"id": 5, "indirizzo": {}}]}}
    lotti = parse_risposta_ricerca(data)
    assert [l.id_esterno for l in lotti] == ["5"]


def test_filtro_provincia_e_residenziale_sulla_fixture():
    # target: provincia di Venezia intera, solo residenziale
    target = TargetGeo(province_intere={"venezia"}, solo_residenziale=True)
    tenuti = filtra_lotti(parse_risposta_ricerca(_fixture()), target)
    # nella fixture: Palermo (scartato: provincia), Venezia commerciale (scartato:
    # tipologia), Venezia residenziale (tenuto)
    assert len(tenuti) == 1
    assert tenuti[0].comune == "Venezia"
    assert tenuti[0].categoria == CATEGORIA_RESIDENZIALE


def test_filtro_disinnesca_la_trappola_del_comune_omonimo():
    # due immobili residenziali "Mogliano": uno in provincia di Treviso (target),
    # uno in provincia di Macerata (omonimo, da scartare)
    lotti = [
        Lotto(fonte="pvp", id_esterno="1", url="u", comune="Mogliano Veneto",
              provincia="Treviso", categoria=CATEGORIA_RESIDENZIALE),
        Lotto(fonte="pvp", id_esterno="2", url="u", comune="Mogliano",
              provincia="Macerata", categoria=CATEGORIA_RESIDENZIALE),
    ]
    target = TargetGeo(
        province_intere=set(),
        comuni_ammessi={("treviso", "mogliano veneto")},
        solo_residenziale=True,
    )
    tenuti = filtra_lotti(lotti, target)
    assert [l.id_esterno for l in tenuti] == ["1"]


def test_filtro_senza_solo_residenziale_tiene_anche_altre_tipologie():
    target = TargetGeo(province_intere={"venezia"}, solo_residenziale=False)
    tenuti = filtra_lotti(parse_risposta_ricerca(_fixture()), target)
    # Venezia commerciale + Venezia residenziale (Palermo resta fuori: provincia)
    assert len(tenuti) == 2
    assert {l.comune for l in tenuti} == {"Venezia"}
