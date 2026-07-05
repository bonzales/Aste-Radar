"""Test della logica deterministica dell'estrattore: schema, prompt, euristica di
escalation. La chiamata reale all'LLM non è testata qui (richiede rete + API key);
si usa un client fittizio per verificare il flusso di escalation."""

from src.extractor import (
    CAMPI_SOSTANZIALI,
    MODELLO_BASE,
    MODELLO_ESCALATION,
    PeriziaEstratta,
    conta_campi_sostanziali,
    costruisci_messaggio,
    estrai_perizia,
    serve_escalation,
)


def test_perizia_estratta_default_tutti_none():
    p = PeriziaEstratta()
    assert p.valore_stima is None
    assert p.occupazione is None
    assert p.note is None


def test_conta_campi_e_soglia_escalation():
    povera = PeriziaEstratta(valore_stima=100000.0)  # 1 campo sostanziale
    ricca = PeriziaEstratta(
        valore_stima=100000.0, prezzo_base=75000.0, superficie_mq=80.0, occupazione="libero"
    )
    assert conta_campi_sostanziali(povera) == 1
    assert conta_campi_sostanziali(ricca) == len(CAMPI_SOSTANZIALI)
    assert serve_escalation(povera) is True
    assert serve_escalation(ricca) is False


def test_costruisci_messaggio_include_testo_e_istruzione():
    msg = costruisci_messaggio("Valore di stima 100000 euro")
    assert "Valore di stima 100000 euro" in msg
    assert "null" in msg  # istruzione a non inventare


def test_parse_json_risposta_tollera_testo_attorno():
    from src.extractor import _parse_json_risposta
    grezzo = 'Ecco i dati:\n```json\n{"valore_stima": 100000, "note": null}\n```\nfine'
    dati = _parse_json_risposta(grezzo)
    assert dati["valore_stima"] == 100000


# --- Fake client per testare il flusso di escalation senza rete ---

class _Blocco:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResp:
    def __init__(self, parsed):
        # il modello "risponde" col JSON dei dati
        self.content = [_Blocco(parsed.model_dump_json())]


class _FakeMessages:
    def __init__(self, per_modello):
        self.per_modello = per_modello
        self.modelli_chiamati = []

    def create(self, model, **kwargs):
        self.modelli_chiamati.append(model)
        return _FakeResp(self.per_modello[model])


class _FakeClient:
    def __init__(self, per_modello):
        self.messages = _FakeMessages(per_modello)


def test_escalation_quando_base_povera_e_forte_migliore():
    per_modello = {
        MODELLO_BASE: PeriziaEstratta(valore_stima=100000.0),  # povera → escalation
        MODELLO_ESCALATION: PeriziaEstratta(
            valore_stima=100000.0, prezzo_base=75000.0, superficie_mq=80.0, occupazione="libero"
        ),
    }
    client = _FakeClient(per_modello)
    risultato = estrai_perizia(client, "testo perizia lungo...")
    # ha chiamato entrambi i modelli e tenuto il risultato più ricco
    assert client.messages.modelli_chiamati == [MODELLO_BASE, MODELLO_ESCALATION]
    assert risultato.occupazione == "libero"
    assert conta_campi_sostanziali(risultato) == 4


def test_nessuna_escalation_se_base_gia_ricca():
    per_modello = {
        MODELLO_BASE: PeriziaEstratta(
            valore_stima=100000.0, prezzo_base=75000.0, superficie_mq=80.0, occupazione="libero"
        ),
    }
    client = _FakeClient(per_modello)
    risultato = estrai_perizia(client, "testo perizia")
    # un solo modello chiamato: niente escalation
    assert client.messages.modelli_chiamati == [MODELLO_BASE]
    assert risultato.prezzo_base == 75000.0


def test_escalation_disabilitata_non_richiama():
    per_modello = {MODELLO_BASE: PeriziaEstratta(valore_stima=100000.0)}
    client = _FakeClient(per_modello)
    risultato = estrai_perizia(client, "testo", modello_escalation=None)
    assert client.messages.modelli_chiamati == [MODELLO_BASE]
    assert risultato.valore_stima == 100000.0
