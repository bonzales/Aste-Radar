"""Estrazione strutturata dei dati della perizia via LLM (CLAUDE.md §3, §7, §9.2).

Il testo grezzo della perizia (da parser.py) viene passato a un modello Anthropic
che restituisce un JSON strutturato con i campi chiave. Regola non negoziabile
(§1.2): un dato NON presente nella perizia torna `null`, mai inventato.

Modello: Haiku 4.5 per l'estrazione di massa, con escalation a un modello più
forte sui casi difficili (§7, deciso 2026-07-05). Output vincolato via structured
outputs (pydantic) così la forma del JSON è garantita.

La parte deterministica (schema, prompt, euristica di escalation, conteggio campi)
è testabile senza rete; la chiamata all'LLM è I/O.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

MODELLO_BASE = "claude-haiku-4-5"
MODELLO_ESCALATION = "claude-sonnet-5"

# Sotto questo numero di campi "sostanziali" valorizzati su una perizia lunga,
# si sospetta un'estrazione povera e si fa escalation al modello più forte.
SOGLIA_ESCALATION = 3
# I campi che contano per decidere l'escalation (i più importanti per lo scoring).
CAMPI_SOSTANZIALI = ("valore_stima", "prezzo_base", "superficie_mq", "occupazione")


class PeriziaEstratta(BaseModel):
    """Dati chiave estratti dalla perizia. Ogni campo è opzionale: se il dato non
    è nella perizia resta None (§1.2). I campi rispecchiano CLAUDE.md §3.2."""

    valore_stima: float | None = Field(
        None, description="Valore di stima dell'immobile in euro (perizia), non il prezzo base d'asta"
    )
    prezzo_base: float | None = Field(
        None, description="Prezzo base d'asta in euro, se indicato nella perizia/avviso"
    )
    superficie_mq: float | None = Field(
        None, description="Superficie in metri quadri; annota nelle note se commerciale o calpestabile"
    )
    indirizzo: str | None = Field(None, description="Indirizzo completo dell'immobile")
    zona: str | None = Field(None, description="Zona/località o riferimento urbanistico, se indicato")
    occupazione: str | None = Field(
        None,
        description="Stato di occupazione: libero, occupato dal debitore, occupato con contratto opponibile, ecc.",
    )
    categoria_catastale: str | None = Field(
        None, description="Categoria catastale (es. A/2, A/3), se indicata"
    )
    difformita: str | None = Field(
        None, description="Difformità/abusi edilizi rilevati; specificare se sanabili o insanabili"
    )
    arretrati_condominiali: float | None = Field(
        None, description="Arretrati condominiali a carico dell'aggiudicatario in euro, se quantificati"
    )
    note: str | None = Field(
        None, description="Note rilevanti per la valutazione non catturate dagli altri campi"
    )


SYSTEM_PROMPT = (
    "Sei un assistente che estrae dati strutturati da perizie immobiliari di aste "
    "giudiziarie italiane. Estrai SOLO ciò che è scritto nella perizia. Se un dato "
    "non è presente o non sei sicuro, lascia il campo null: NON stimare, NON dedurre, "
    "NON inventare. Un valore falso in una perizia d'asta può costare decine di "
    "migliaia di euro. Distingui il VALORE DI STIMA peritale dal PREZZO BASE d'asta. "
    "Il testo può provenire da OCR e contenere rumore: ignoralo."
)


def costruisci_messaggio(testo_perizia: str) -> str:
    return (
        "Estrai i dati chiave dalla seguente perizia. Ricorda: campo non presente = null.\n\n"
        "=== PERIZIA ===\n" + testo_perizia
    )


def conta_campi_sostanziali(estratta: PeriziaEstratta) -> int:
    return sum(getattr(estratta, c) is not None for c in CAMPI_SOSTANZIALI)


def serve_escalation(estratta: PeriziaEstratta) -> bool:
    """True se l'estrazione pare troppo povera e conviene riprovare col modello forte."""
    return conta_campi_sostanziali(estratta) < SOGLIA_ESCALATION


def _estrai_con_modello(client, testo_perizia: str, modello: str) -> PeriziaEstratta:
    resp = client.messages.parse(
        model=modello,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": costruisci_messaggio(testo_perizia)}],
        output_format=PeriziaEstratta,
    )
    return resp.parsed_output


def estrai_perizia(
    client,
    testo_perizia: str,
    modello_base: str = MODELLO_BASE,
    modello_escalation: str | None = MODELLO_ESCALATION,
) -> PeriziaEstratta:
    """Estrae i dati dalla perizia. Prova col modello base; se l'esito è povero e
    l'escalation è abilitata, riprova una volta col modello forte e tiene il
    risultato migliore (più campi sostanziali valorizzati)."""
    estratta = _estrai_con_modello(client, testo_perizia, modello_base)
    if modello_escalation and serve_escalation(estratta):
        forte = _estrai_con_modello(client, testo_perizia, modello_escalation)
        if conta_campi_sostanziali(forte) > conta_campi_sostanziali(estratta):
            return forte
    return estratta
