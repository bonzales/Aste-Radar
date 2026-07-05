"""Test della griglia di screening (scorer): gate hard, scarto/segnala, punteggio.

Il cuore decisionale: TDD pieno (§9.2). Usa una griglia sintetica coerente con
config/scoring.yaml (soglie decise 2026-07-05)."""

import pytest

from src.extractor import PeriziaEstratta
from src.models import Lotto
from src.scorer import Esito, carica_griglia, valuta

GRIGLIA = {
    "tarato": True,
    "hard": {
        "sconto_min_su_stima": 0.25,
        "prezzo_base_max": 150000,
        "occupazione_ammessa": ["libero", "occupato_debitore"],
        "solo_piena_proprieta": True,
        "categorie_ammesse": ["A/2", "A/3", "A/7"],
        "scarta_se_abusi_insanabili": True,
        "superficie_mq_min": None,
        "superficie_mq_max": None,
    },
    "soft": {"peso_sconto_su_stima": 1.0},
}


def _lotto(prezzo_base=100000.0):
    return Lotto(fonte="pvp", id_esterno="1", url="u", prezzo_base=prezzo_base)


def _perizia_buona(**over):
    base = dict(
        valore_stima=150000.0,      # prezzo 100k → sconto 33%
        occupazione_tipo="libero",
        piena_proprieta=True,
        categoria_catastale="A/2",
        abusi_insanabili=False,
    )
    base.update(over)
    return PeriziaEstratta(**base)


def test_lotto_conforme_passa_con_motivazione_e_punteggio():
    e = valuta(_lotto(), _perizia_buona(), GRIGLIA)
    assert e.passa is True
    assert not e.scarti and not e.da_verificare
    assert round(e.sconto, 2) == 0.33
    assert 0 < e.punteggio <= 1
    breve = e.motivazione_breve()
    assert "sotto stima" in breve and "libero" in breve and "A/2" in breve


def test_sconto_insufficiente_scarta():
    # prezzo 130k su stima 150k → sconto 13% < 25%
    e = valuta(_lotto(130000.0), _perizia_buona(), GRIGLIA)
    assert e.passa is False
    assert any("sconto" in s for s in e.scarti)


def test_prezzo_oltre_budget_scarta():
    e = valuta(_lotto(160000.0), _perizia_buona(valore_stima=300000.0), GRIGLIA)
    assert e.passa is False
    assert any("tetto" in s for s in e.scarti)


def test_occupazione_con_contratto_scarta():
    e = valuta(_lotto(), _perizia_buona(occupazione_tipo="occupato_contratto"), GRIGLIA)
    assert e.passa is False
    assert any("occupazione" in s for s in e.scarti)


def test_occupato_dal_debitore_e_ammesso():
    e = valuta(_lotto(), _perizia_buona(occupazione_tipo="occupato_debitore"), GRIGLIA)
    assert e.passa is True


def test_non_piena_proprieta_scarta():
    e = valuta(_lotto(), _perizia_buona(piena_proprieta=False), GRIGLIA)
    assert e.passa is False
    assert any("piena proprietà" in s for s in e.scarti)


def test_categoria_non_ammessa_scarta():
    # D/2 (albergo) come il caso reale della Giudecca
    e = valuta(_lotto(), _perizia_buona(categoria_catastale="D/2"), GRIGLIA)
    assert e.passa is False
    assert any("categoria" in s for s in e.scarti)


def test_abusi_insanabili_scarta():
    e = valuta(_lotto(), _perizia_buona(abusi_insanabili=True), GRIGLIA)
    assert e.passa is False
    assert any("insanabili" in s for s in e.scarti)


def test_dato_mancante_non_notifica_ma_non_scarta():
    # occupazione non classificata → da verificare, non passa (ma non è uno scarto hard)
    e = valuta(_lotto(), _perizia_buona(occupazione_tipo=None), GRIGLIA)
    assert e.passa is False
    assert e.scarti == []
    assert any("occupazione" in v for v in e.da_verificare)


def test_superficie_fuori_range_scarta():
    g = {**GRIGLIA, "hard": {**GRIGLIA["hard"], "superficie_mq_min": 40, "superficie_mq_max": 200}}
    e = valuta(_lotto(), _perizia_buona(superficie_mq=1200.0), g)
    assert e.passa is False
    assert any("superficie" in s for s in e.scarti)


def test_carica_griglia_rifiuta_non_tarata(tmp_path):
    p = tmp_path / "scoring.yaml"
    p.write_text("tarato: false\nhard: {}\n", encoding="utf-8")
    with pytest.raises(RuntimeError):
        carica_griglia(p)
