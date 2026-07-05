"""Test della formattazione del messaggio Telegram (deterministica)."""

from src.models import Lotto
from src.notifier import formatta_messaggio


def test_messaggio_completo():
    l = Lotto(
        fonte="pvp", id_esterno="1",
        url="https://pvp.giustizia.it/pvp/it/detail_annuncio.page?idAnnuncio=1",
        comune="Venezia", provincia="Venezia",
        titolo="Appartamento al primo piano", prezzo_base=112500.0,
        data_vendita="2026-09-01",
    )
    msg = formatta_messaggio(l)
    assert "🏠 Appartamento al primo piano" in msg
    assert "📍 Venezia (Venezia)" in msg
    assert "💶 Base: € 112.500" in msg
    assert "🗓 Vendita: 2026-09-01" in msg
    assert "idAnnuncio=1" in msg


def test_messaggio_promosso_ha_spunta_e_motivazione():
    l = Lotto(fonte="pvp", id_esterno="9", url="u", comune="Gruaro", provincia="Venezia",
              titolo="Casa", esito_stato="passa", punteggio=0.9,
              motivazione="prezzo 59% sotto stima, libero, cat. A/5")
    msg = formatta_messaggio(l)
    assert "✅ prezzo 59% sotto stima" in msg
    assert "★" in msg  # stelle dal punteggio


def test_messaggio_verifica_ha_avviso():
    l = Lotto(fonte="pvp", id_esterno="9", url="u", comune="Fossalta", provincia="Venezia",
              titolo="Appartamento", esito_stato="verifica",
              motivazione="manca: occupazione non classificata")
    msg = formatta_messaggio(l)
    assert "⚠️" in msg and "DA VERIFICARE" in msg
    assert "occupazione" in msg


def test_campi_assenti_vengono_omessi_non_inventati():
    l = Lotto(fonte="pvp", id_esterno="2", url="u", comune="Mestre",
              provincia="Venezia", titolo=None, prezzo_base=None, data_vendita=None)
    msg = formatta_messaggio(l)
    # niente riga prezzo/vendita se i dati mancano
    assert "Base:" not in msg
    assert "Vendita:" not in msg
    # titolo assente → fallback generico, non un valore falso
    assert "🏠 Nuovo lotto" in msg
    assert "📍 Mestre (Venezia)" in msg
