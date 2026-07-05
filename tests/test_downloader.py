"""Test della logica deterministica del downloader (Fase 2): parsing allegati,
costruzione URL, nome file sicuro, e idempotenza del salvataggio in raw/."""

import json
from pathlib import Path

from src.downloader import (
    Allegato,
    nome_file_sicuro,
    parse_allegati,
    scarica_allegati,
    url_download,
)

FIXTURE = Path("tests/fixtures/pvp/dettaglio-allegati.json")


def test_parse_allegati_dalla_fixture_reale():
    dett = json.loads(FIXTURE.read_text(encoding="utf-8"))
    allegati = parse_allegati(dett)
    assert len(allegati) == 3
    # la perizia è riconosciuta per codice tipo
    perizie = [a for a in allegati if a.is_perizia]
    assert len(perizie) == 1
    assert perizie[0].tipo_leggibile == "perizia"
    assert perizie[0].nome_file.endswith(".pdf")


def test_parse_scarta_allegati_senza_link_o_id():
    dett = {"body": {"allegati": [
        {"idAllegato": 1, "nomeFile": "ok.pdf", "linkAllegato": "/allegati/1/ok.pdf"},
        {"idAllegato": 2, "nomeFile": "senza-link.pdf"},          # no link
        {"nomeFile": "senza-id.pdf", "linkAllegato": "/allegati/x"},  # no id
    ]}}
    allegati = parse_allegati(dett)
    assert [a.id_allegato for a in allegati] == ["1"]


def test_url_download_codifica_gli_spazi():
    link = "/allegati/4604105/perizia con spazi (1).pdf?versionId=abc-123"
    url = url_download(link)
    assert url.startswith("https://resource-pvp.giustizia.it/allegati/4604105/")
    assert " " not in url.split("?")[0]        # path codificato
    assert url.endswith("?versionId=abc-123")  # query preservata


def test_nome_file_sicuro_rimuove_separatori_di_percorso():
    assert "/" not in nome_file_sicuro("../../etc/passwd")
    assert "\\" not in nome_file_sicuro("cartella\\file.pdf")
    assert nome_file_sicuro("  ") == "allegato"


class _FakeClient:
    def __init__(self, dett):
        self._dett = dett

    def dettaglio_vendita(self, id_lotto):
        return self._dett


class _FakeHttp:
    """Simula lo stream di download scrivendo un contenuto fittizio."""

    def __init__(self):
        self.scaricati = 0

    def stream(self, method, url):
        self.scaricati += 1
        fake = self

        class _Ctx:
            def __enter__(self_):
                return self_
            def __exit__(self_, *a):
                return False
            def raise_for_status(self_):
                pass
            def iter_bytes(self_, chunk_size=65536):
                yield b"%PDF-fake-content"
        return _Ctx()


def _lotto(id_esterno="999"):
    from src.models import Lotto
    return Lotto(fonte="pvp", id_esterno=id_esterno, url="u", prima_vista_il="2026-07-05")


def test_scarica_allegati_salva_in_raw_con_struttura_data_id(tmp_path):
    dett = json.loads(FIXTURE.read_text(encoding="utf-8"))
    salvati = scarica_allegati(_FakeClient(dett), _lotto(), dir_base=tmp_path, http=_FakeHttp())
    assert len(salvati) == 3
    assert all(p.exists() for p in salvati)
    # struttura raw/<data>/<id_lotto>/
    assert salvati[0].parent.name == "999"
    assert salvati[0].parent.parent.name == "2026-07-05"


def test_scarica_allegati_non_ri_scarica_file_gia_completo(tmp_path):
    contenuto = b"%PDF-fake-content"
    # un allegato la cui dimensione dichiarata combacia col contenuto fake
    dett = {"body": {"allegati": [
        {"idAllegato": 7, "nomeFile": "perizia.pdf",
         "linkAllegato": "/allegati/999/perizia.pdf?versionId=z",
         "dimensioneAllegato": len(contenuto), "codiceTipoAllegato": "PERIZ"},
    ]}}
    http1 = _FakeHttp()
    scarica_allegati(_FakeClient(dett), _lotto(), dir_base=tmp_path, http=http1)
    assert http1.scaricati == 1                     # primo giro: scarica

    http2 = _FakeHttp()
    scarica_allegati(_FakeClient(dett), _lotto(), dir_base=tmp_path, http=http2)
    assert http2.scaricati == 0                     # idempotente: già presente
