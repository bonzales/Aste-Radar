"""Griglia di screening: decide se un lotto si NOTIFICA o si SCARTA (CLAUDE.md §5).

È il cuore decisionale. Applica i criteri HARD di `config/scoring.yaml` combinando:
- i dati della ricerca (prezzo base d'asta) — dal Lotto;
- i dati estratti dalla perizia (valore stima, occupazione, proprietà, categoria,
  abusi) — dalla PeriziaEstratta.

Regola (§5): un lotto si notifica solo se supera TUTTI i gate hard con certezza.
Un criterio hard fallito → scarto. Un dato mancante che impedisce di verificare un
gate → il lotto NON si notifica (resta in DB, recuperabile) e si segnala cosa manca.
Nessun ammorbidimento: in asta la disciplina batte il volume.

Logica deterministica e testabile in isolamento → TDD pieno (§9.2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Esito:
    passa: bool
    sconto: float | None                       # 0..1, es. 0.32 = 32% sotto stima
    punteggio: float | None                    # soft 0..1 (solo se passa)
    motivazioni: list[str] = field(default_factory=list)   # perché è interessante
    scarti: list[str] = field(default_factory=list)        # gate hard falliti
    da_verificare: list[str] = field(default_factory=list)  # dati mancanti

    def motivazione_breve(self) -> str:
        return ", ".join(self.motivazioni)

    def codice(self) -> int:
        """1 = passa (notifica ✅); 2 = promettente ma con dati mancanti (notifica
        ⚠️ da verificare a mano); 0 = scartato (silenzio, §5)."""
        if self.passa:
            return 1
        if self.scarti:
            return 0
        if self.da_verificare:
            return 2
        return 0

    def stato(self) -> str:
        return {1: "passa", 2: "verifica", 0: "scarta"}[self.codice()]

    def riassunto(self) -> str:
        """Testo sintetico dell'esito, per DB e notifica."""
        if self.passa:
            return self.motivazione_breve()
        if self.scarti:
            return "SCARTO: " + "; ".join(self.scarti)
        if self.da_verificare:
            return "manca: " + "; ".join(self.da_verificare)
        return "scartato"


def carica_griglia(path: str | Path = "config/scoring.yaml") -> dict:
    dati = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not dati.get("tarato"):
        raise RuntimeError(
            "config/scoring.yaml non è 'tarato': la griglia non è pronta per la produzione."
        )
    return dati


def _categoria_norm(cat: str | None) -> str | None:
    """Estrae la sigla catastale tipo 'A/2' da una stringa libera."""
    if not cat:
        return None
    m = re.search(r"\b([A-F]/\d{1,2})\b", cat.upper().replace(" ", ""))
    return m.group(1) if m else cat.strip().upper()


def valuta(lotto, perizia, griglia: dict) -> Esito:
    """Applica i gate hard a un lotto + la sua perizia estratta."""
    hard = griglia.get("hard", {})
    esito = Esito(passa=False, sconto=None, punteggio=None)

    prezzo = lotto.prezzo_base
    stima = perizia.valore_stima

    # --- Gate 1: tetto di prezzo base ---
    tetto = hard.get("prezzo_base_max")
    if prezzo is None:
        esito.da_verificare.append("prezzo base mancante")
    elif tetto is not None and prezzo > tetto:
        esito.scarti.append(f"prezzo base {prezzo:,.0f}€ oltre il tetto {tetto:,.0f}€")

    # --- Gate 2: sconto minimo sulla stima ---
    soglia_sconto = hard.get("sconto_min_su_stima")
    if prezzo is None or not stima:
        esito.da_verificare.append("sconto non calcolabile (manca prezzo o valore di stima)")
    else:
        sconto = 1 - (prezzo / stima)
        esito.sconto = sconto
        if soglia_sconto is not None and sconto < soglia_sconto:
            esito.scarti.append(
                f"sconto {sconto*100:.0f}% sotto la soglia {soglia_sconto*100:.0f}%"
            )

    # --- Gate 3: occupazione ammessa ---
    ammesse_occ = hard.get("occupazione_ammessa") or []
    if perizia.occupazione_tipo is None:
        esito.da_verificare.append("occupazione non classificata")
    elif ammesse_occ and perizia.occupazione_tipo not in ammesse_occ:
        esito.scarti.append(f"occupazione '{perizia.occupazione_tipo}' non ammessa")

    # --- Gate 4: piena proprietà ---
    if hard.get("solo_piena_proprieta"):
        if perizia.piena_proprieta is True:
            pass
        elif perizia.piena_proprieta is False:
            esito.scarti.append("non è piena proprietà (quota/nuda proprietà/usufrutto)")
        else:
            esito.da_verificare.append("piena proprietà da confermare")

    # --- Gate 5: categoria catastale ammessa ---
    ammesse_cat = [c.upper() for c in (hard.get("categorie_ammesse") or [])]
    cat = _categoria_norm(perizia.categoria_catastale)
    if cat is None:
        esito.da_verificare.append("categoria catastale mancante")
    elif ammesse_cat and cat not in ammesse_cat:
        esito.scarti.append(f"categoria {cat} non ammessa")

    # --- Gate 6: abusi insanabili ---
    if hard.get("scarta_se_abusi_insanabili") and perizia.abusi_insanabili is True:
        esito.scarti.append("abusi/difformità insanabili")

    # --- Gate 7: superficie ---
    smin, smax = hard.get("superficie_mq_min"), hard.get("superficie_mq_max")
    sup = perizia.superficie_mq
    if (smin is not None or smax is not None):
        if sup is None:
            esito.da_verificare.append("superficie mancante")
        else:
            if smin is not None and sup < smin:
                esito.scarti.append(f"superficie {sup:.0f}mq sotto il minimo {smin:.0f}mq")
            if smax is not None and sup > smax:
                esito.scarti.append(f"superficie {sup:.0f}mq oltre il massimo {smax:.0f}mq")

    # --- Verdetto ---
    esito.passa = not esito.scarti and not esito.da_verificare
    if esito.passa:
        esito.motivazioni = _motivazioni(lotto, perizia, esito)
        esito.punteggio = _punteggio(esito.sconto, soglia_sconto, griglia)
    return esito


def _motivazioni(lotto, perizia, esito: Esito) -> list[str]:
    m: list[str] = []
    if esito.sconto is not None:
        m.append(f"prezzo {esito.sconto*100:.0f}% sotto stima")
    occ = {"libero": "libero", "occupato_debitore": "occupato dal debitore (liberabile)"}
    if perizia.occupazione_tipo in occ:
        m.append(occ[perizia.occupazione_tipo])
    if perizia.categoria_catastale:
        m.append(f"cat. {_categoria_norm(perizia.categoria_catastale)}")
    if perizia.superficie_mq:
        m.append(f"{perizia.superficie_mq:.0f} mq")
    if lotto.prezzo_base is not None:
        m.append(f"base {lotto.prezzo_base:,.0f}€".replace(",", "."))
    return m


def _punteggio(sconto: float | None, soglia: float | None, griglia: dict) -> float | None:
    if sconto is None or soglia is None:
        return None
    peso = (griglia.get("soft") or {}).get("peso_sconto_su_stima", 1.0)
    # normalizza lo sconto sopra la soglia in 0..1
    grezzo = (sconto - soglia) / (1 - soglia) if soglia < 1 else 0.0
    return max(0.0, min(1.0, grezzo)) * peso
