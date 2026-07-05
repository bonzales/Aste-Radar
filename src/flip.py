"""Livello 3 — stima del margine di flip (CLAUDE.md §11, §4 Fase 4).

Dal prezzo d'acquisto (base d'asta), dal valore di stima peritale e dalla
superficie, stima il MARGINE NETTO di una rivendita entro 5 anni, sottraendo le
voci di costo: imposte d'acquisto, ristrutturazione, costi di procedura/possesso/
rivendita e la tassazione della plusvalenza.

NON è consulenza fiscale (§1.6): è una STIMA di screening con assunzioni esplicite
e configurabili (config/scoring.yaml → `flip:`). La decisione finale è umana.
Calcolo deterministico → TDD sempre (§9.2).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MargineFlip:
    prezzo_acquisto: float
    rivendita: float
    imposta_acquisto: float
    ristrutturazione: float
    costi_procedura: float
    costi_possesso: float
    costi_rivendita: float
    plusvalenza_tassata: float
    investimento_totale: float   # capitale che devi mettere (acquisto + costi)
    margine_netto: float         # utile netto stimato dopo tasse
    margine_pct: float           # margine_netto / investimento_totale

    def riga(self) -> str:
        return f"margine netto stim. {self.margine_netto:,.0f}€ ({self.margine_pct*100:.0f}%)".replace(",", ".")


def _cfg(griglia: dict) -> dict:
    return griglia.get("flip", {}) or {}


def flip_abilitato(griglia: dict) -> bool:
    return bool(griglia.get("calcola_margine_flip"))


def calcola_margine(
    prezzo_acquisto: float | None,
    valore_stima: float | None,
    superficie_mq: float | None,
    griglia: dict,
) -> MargineFlip | None:
    """Stima il margine netto di flip. Ritorna None se mancano i dati essenziali
    (nessuna invenzione, §1.2)."""
    if not prezzo_acquisto or not valore_stima or not superficie_mq:
        return None
    c = _cfg(griglia)
    rivendita = valore_stima * c.get("rivendita_su_stima", 1.0)
    imposta_acquisto = prezzo_acquisto * c.get("imposta_acquisto_pct", 0.10)
    ristrutturazione = superficie_mq * c.get("ristrutturazione_eur_mq", 0.0)
    costi_procedura = prezzo_acquisto * c.get("costi_procedura_pct", 0.03)
    costi_possesso = c.get("costi_possesso_mensili", 0.0) * c.get("mesi_possesso", 0)
    costi_rivendita = rivendita * c.get("costi_rivendita_pct", 0.04)

    investimento = (prezzo_acquisto + imposta_acquisto + ristrutturazione
                    + costi_procedura + costi_possesso)
    plusvalenza_lorda = rivendita - costi_rivendita - investimento
    tassa = max(0.0, plusvalenza_lorda) * c.get("plusvalenza_pct", 0.26)
    margine_netto = plusvalenza_lorda - tassa
    margine_pct = margine_netto / investimento if investimento else 0.0

    return MargineFlip(
        prezzo_acquisto=prezzo_acquisto,
        rivendita=rivendita,
        imposta_acquisto=imposta_acquisto,
        ristrutturazione=ristrutturazione,
        costi_procedura=costi_procedura,
        costi_possesso=costi_possesso,
        costi_rivendita=costi_rivendita,
        plusvalenza_tassata=tassa,
        investimento_totale=investimento,
        margine_netto=margine_netto,
        margine_pct=margine_pct,
    )
