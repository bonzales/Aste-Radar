"""Test della logica del bot a comandi: gate di sicurezza (solo chat autorizzato),
dispatch dei comandi e formattazione. Il long-polling (I/O) non è testato qui."""

import sqlite3

import pytest

from src import bot, db


@pytest.fixture()
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    db.init_db(c)
    # un promosso, un da verificare, uno scartato, uno non ancora analizzato
    c.execute(
        "INSERT INTO lotti (fonte,id_esterno,url,comune,provincia,titolo,prezzo_base,"
        "data_vendita,prima_vista_il,analizzato_il,esito_passa,punteggio,motivazione) "
        "VALUES ('pvp','111','http://x/111','Chioggia','Venezia','Bilocale',90000,"
        "'2026-08-01','2026-07-05','2026-07-05',1,0.8,'PASSA: 31% sotto stima')"
    )
    c.execute(
        "INSERT INTO lotti (fonte,id_esterno,comune,provincia,prezzo_base,prima_vista_il,"
        "analizzato_il,esito_passa,motivazione) VALUES ('pvp','222','Mira','Venezia',100000,"
        "'2026-07-05','2026-07-05',0,'SCARTO: sotto soglia')"
    )
    c.execute(
        "INSERT INTO lotti (fonte,id_esterno,comune,provincia,prezzo_base,prima_vista_il) "
        "VALUES ('pvp','333','Venezia','Venezia',80000,'2026-07-05')"
    )
    c.commit()
    yield c
    c.close()


GRIGLIA = {
    "hard": {
        "sconto_min_su_stima": 0.25,
        "prezzo_base_max": 150000,
        "occupazione_ammessa": ["libero", "occupato_debitore"],
        "solo_piena_proprieta": True,
        "categorie_ammesse": ["A/2", "A/3"],
        "superficie_mq_min": None,
        "superficie_mq_max": None,
    },
    "calcola_margine_flip": True,
    "flip": {"rivendita_su_stima": 1.0, "ristrutturazione_eur_mq": 400},
}


# --- sicurezza: solo i chat autorizzati ---

def test_messaggio_da_chat_autorizzato_passa():
    upd = {"update_id": 1, "message": {"chat": {"id": 1288729394}, "text": "/status"}}
    assert bot.messaggio_autorizzato(upd, "1288729394") == "/status"


def test_messaggio_da_altro_chat_ignorato():
    upd = {"update_id": 1, "message": {"chat": {"id": 999}, "text": "/status"}}
    assert bot.messaggio_autorizzato(upd, "1288729394") is None


def test_update_senza_messaggio_ignorato():
    assert bot.messaggio_autorizzato({"update_id": 1}, "1288729394") is None


def test_piu_chat_autorizzati_da_lista_separata_da_virgola():
    autorizzati = bot.chat_autorizzati("1288729394, 987654321")
    assert autorizzati == {"1288729394", "987654321"}
    upd = {"update_id": 1, "message": {"chat": {"id": 987654321}, "text": "/status"}}
    # un secondo id (es. la persona con cui condivido) è autorizzato
    assert bot.messaggio_autorizzato(upd, "1288729394,987654321") == "/status"


def test_estrai_chat_e_testo():
    upd = {"update_id": 1, "message": {"chat": {"id": 555}, "text": "/lotto 1"}}
    assert bot.estrai_chat_e_testo(upd) == ("555", "/lotto 1")


def test_testo_non_autorizzato_contiene_lid_per_aggiungerlo():
    msg = bot.testo_non_autorizzato("987654321")
    assert "987654321" in msg
    assert "non è autorizzato" in msg.lower()


# --- dispatch dei comandi ---

def test_help_elenca_comandi(conn):
    r = bot.gestisci_comando("/help", conn=conn, griglia=GRIGLIA)
    assert "/status" in r and "/scan" in r and "/lotto" in r


def test_status_conta_gli_esiti(conn):
    r = bot.gestisci_comando("/status", conn=conn, griglia=GRIGLIA)
    assert "Lotti in memoria: 3" in r
    assert "Ancora da analizzare: 1" in r
    assert "Promossi: 1" in r
    assert "Scartati: 1" in r


def test_lotto_mostra_dettaglio(conn):
    r = bot.gestisci_comando("/lotto 111", conn=conn, griglia=GRIGLIA)
    assert "Chioggia" in r
    assert "31% sotto stima" in r
    assert "promosso" in r


def test_lotto_inesistente(conn):
    r = bot.gestisci_comando("/lotto 999", conn=conn, griglia=GRIGLIA)
    assert "Nessun lotto" in r


def test_lotto_senza_argomento(conn):
    r = bot.gestisci_comando("/lotto", conn=conn, griglia=GRIGLIA)
    assert "Uso:" in r


def test_soglie_mostra_griglia(conn):
    r = bot.gestisci_comando("/soglie", conn=conn, griglia=GRIGLIA)
    assert "25%" in r          # sconto minimo
    assert "150.000" in r      # prezzo base max formattato
    assert "libero" in r


def test_scan_invoca_avvio_e_conferma(conn):
    chiamato = []
    r = bot.gestisci_comando("/scan", conn=conn, griglia=GRIGLIA,
                             avvia_scan=lambda: chiamato.append(True))
    assert chiamato == [True]
    assert "avviata" in r.lower()


def test_scan_senza_avvio_disponibile(conn):
    r = bot.gestisci_comando("/scan", conn=conn, griglia=GRIGLIA, avvia_scan=None)
    assert "non disponibile" in r.lower()


def test_rinvia_invoca_avvio_e_conferma(conn):
    chiamato = []
    r = bot.gestisci_comando("/rinvia", conn=conn, griglia=GRIGLIA,
                             avvia_reinvio=lambda: chiamato.append(True))
    assert chiamato == [True]
    assert "re-invio" in r.lower()


def test_comando_sconosciuto(conn):
    r = bot.gestisci_comando("/pippo", conn=conn, griglia=GRIGLIA)
    assert "sconosciuto" in r.lower()


def test_linguaggio_libero_rimanda_a_help(conn):
    r = bot.gestisci_comando("ciao come va", conn=conn, griglia=GRIGLIA)
    assert "/help" in r


def test_comando_con_mention_bot(conn):
    # in Telegram i comandi possono arrivare come /status@NomeBot
    r = bot.gestisci_comando("/status@AsteRadarBot", conn=conn, griglia=GRIGLIA)
    assert "Lotti in memoria" in r
