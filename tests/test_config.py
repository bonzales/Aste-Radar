"""Test del caricamento del target geografico da config/comuni.yaml."""

from src.config import carica_target


def test_carica_target_dal_config_reale():
    t = carica_target("config/comuni.yaml")
    # provincia di Venezia presa per intero
    assert "venezia" in t.province_intere
    # i comuni TV confermati sono ammessi
    assert ("treviso", "mogliano veneto") in t.comuni_ammessi
    assert ("treviso", "treviso") in t.comuni_ammessi
    # tipologia: solo residenziale
    assert t.solo_residenziale is True


def test_ammette_provincia_intera_e_comuni_extra():
    t = carica_target("config/comuni.yaml")
    # qualsiasi comune della provincia di Venezia
    assert t.ammette("Venezia", "Chioggia") is True
    assert t.ammette("Venezia", "Mestre") is True
    # comune TV in lista
    assert t.ammette("Treviso", "Mogliano Veneto") is True


def test_non_ammette_fuori_area():
    t = carica_target("config/comuni.yaml")
    # comune TV NON in lista (provincia Treviso non è presa per intero)
    assert t.ammette("Treviso", "Castelfranco Veneto") is False
    # la trappola: Mogliano in provincia di Macerata NON deve passare
    assert t.ammette("Macerata", "Mogliano") is False
    assert t.ammette("Milano", "Milano") is False
