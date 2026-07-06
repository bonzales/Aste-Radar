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


def test_parse_json_ignora_prosa_dopo_oggetto():
    # il match greedy prendeva fino all'ultima '}': con prosa che contiene graffe
    # rompeva. L'estrattore bilanciato si ferma alla chiusura del primo oggetto.
    from src.extractor import _parse_json_risposta
    grezzo = '{"valore_stima": 100000, "note": "libero"}\nNota: vedi punto {3} del testo.'
    dati = _parse_json_risposta(grezzo)
    assert dati["valore_stima"] == 100000
    assert dati["note"] == "libero"


def test_parse_json_tollera_virgola_pendente():
    from src.extractor import _parse_json_risposta
    dati = _parse_json_risposta('{"valore_stima": 100000, "note": null,}')
    assert dati["valore_stima"] == 100000


def test_parse_json_troncato_solleva_errore_chiaro():
    from src.extractor import _parse_json_risposta
    import pytest
    with pytest.raises(ValueError, match="incompleto|troncato"):
        _parse_json_risposta('{"valore_stima": 100000, "note": "manca la chiusura')


def test_schema_json_pulito_senza_commenti():
    # il template NON deve contenere '//' (il modello li copiava rompendo il JSON)
    from src.extractor import _schema_json
    assert "//" not in _schema_json()


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
        self.ultimi_kwargs = {}

    def create(self, model, **kwargs):
        self.modelli_chiamati.append(model)
        self.ultimi_kwargs = kwargs
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


class _RespGrezza:
    """Risposta con un testo arbitrario (per simulare JSON valido o rotto)."""
    def __init__(self, testo):
        self.content = [_Blocco(testo)]


class _MessagesGrezzi:
    def __init__(self, per_modello):
        self.per_modello = per_modello
        self.modelli_chiamati = []

    def create(self, model, **kwargs):
        self.modelli_chiamati.append(model)
        return _RespGrezza(self.per_modello[model])


class _ClientGrezzo:
    def __init__(self, per_modello):
        self.messages = _MessagesGrezzi(per_modello)


def test_escalation_quando_json_base_e_rotto():
    # il modello base restituisce JSON non valido → si passa al modello forte,
    # che risponde con JSON valido: l'estrazione non deve fallire.
    valido = '{"valore_stima": 120000, "occupazione": "libero"}'
    client = _ClientGrezzo({MODELLO_BASE: "non è json {rotto", MODELLO_ESCALATION: valido})
    risultato = estrai_perizia(client, "testo perizia")
    assert client.messages.modelli_chiamati == [MODELLO_BASE, MODELLO_ESCALATION]
    assert risultato.valore_stima == 120000


def test_json_base_rotto_senza_escalation_propaga():
    import pytest
    client = _ClientGrezzo({MODELLO_BASE: "non è json {rotto"})
    with pytest.raises(ValueError):
        estrai_perizia(client, "testo", modello_escalation=None)


def test_verifica_ai_fa_una_chiamata_minima():
    from src.extractor import verifica_ai
    per_modello = {MODELLO_BASE: PeriziaEstratta()}
    client = _FakeClient(per_modello)
    verifica_ai(client)  # non deve sollevare
    assert client.messages.modelli_chiamati == [MODELLO_BASE]
    # preflight economico: max 1 token
    assert client.messages.ultimi_kwargs["max_tokens"] == 1


def test_verifica_ai_propaga_errore_chiave():
    class _Boom:
        def create(self, model, **kwargs):
            raise RuntimeError("401 authentication_error")

    class _ClientBoom:
        messages = _Boom()

    from src.extractor import verifica_ai
    import pytest
    with pytest.raises(RuntimeError, match="authentication_error"):
        verifica_ai(_ClientBoom())
