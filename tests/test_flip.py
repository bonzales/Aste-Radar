"""Test del calcolo del margine di flip (Livello 3). Calcolo finanziario → TDD."""

from src.flip import calcola_margine, flip_abilitato

GRIGLIA = {
    "calcola_margine_flip": True,
    "flip": {
        "rivendita_su_stima": 1.0,
        "ristrutturazione_eur_mq": 400,
        "imposta_acquisto_pct": 0.10,
        "costi_procedura_pct": 0.03,
        "costi_rivendita_pct": 0.04,
        "costi_possesso_mensili": 150,
        "mesi_possesso": 9,
        "plusvalenza_pct": 0.26,
    },
}


def test_flip_abilitato():
    assert flip_abilitato(GRIGLIA) is True
    assert flip_abilitato({"calcola_margine_flip": False}) is False
    assert flip_abilitato({}) is False


def test_margine_calcolato_correttamente():
    # acquisto 100k, stima 150k, 80 mq
    m = calcola_margine(100000, 150000, 80, GRIGLIA)
    assert m is not None
    assert m.rivendita == 150000
    assert m.imposta_acquisto == 10000        # 10% di 100k
    assert m.ristrutturazione == 32000        # 80 * 400
    assert m.costi_procedura == 3000          # 3% di 100k
    assert m.costi_possesso == 1350           # 150 * 9
    assert m.costi_rivendita == 6000          # 4% di 150k
    # investimento = 100000+10000+32000+3000+1350 = 146350
    assert m.investimento_totale == 146350
    # plusvalenza lorda = 150000 - 6000 - 146350 = -2350 → tassa 0, margine negativo
    assert round(m.plusvalenza_tassata) == 0
    assert round(m.margine_netto) == -2350


def test_margine_positivo_e_tassa_plusvalenza():
    # acquisto 60k, stima 150k (sconto forte), 80 mq
    m = calcola_margine(60000, 150000, 80, GRIGLIA)
    # investimento = 60000 + 6000(imp) + 32000(ristr) + 1800(proc) + 1350 = 101150
    assert m.investimento_totale == 101150
    # plusvalenza lorda = 150000 - 6000(riv) - 101150 = 42850
    assert round(m.plusvalenza_tassata) == round(42850 * 0.26)   # 11141
    assert round(m.margine_netto) == round(42850 - 42850 * 0.26)  # 31709
    assert m.margine_pct > 0


def test_dati_mancanti_ritorna_none():
    assert calcola_margine(None, 150000, 80, GRIGLIA) is None
    assert calcola_margine(100000, None, 80, GRIGLIA) is None
    assert calcola_margine(100000, 150000, None, GRIGLIA) is None


def test_riga_leggibile():
    m = calcola_margine(60000, 150000, 80, GRIGLIA)
    r = m.riga()
    assert "margine netto stim." in r and "€" in r and "%" in r
