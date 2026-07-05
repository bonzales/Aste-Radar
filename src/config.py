"""Caricamento del target geografico da config/comuni.yaml (CLAUDE.md §8).

Traduce la config (province per sigla + comuni_extra) nelle regole di filtro che
lo scraper applica lato client sui risultati del PVP. Il PVP restituisce la
provincia col nome esteso (es. "Venezia"), quindi qui si normalizza tutto a nome.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Sigle provincia -> nome esteso come compare nell'indirizzo del PVP.
# Coperte le province del Veneto orientale che ci interessano; estendere se serve.
SIGLA_PROVINCIA = {
    "VE": "Venezia",
    "TV": "Treviso",
    "PD": "Padova",
    "RO": "Rovigo",
    "VR": "Verona",
    "VI": "Vicenza",
    "BL": "Belluno",
}


def _norm(s: str | None) -> str:
    return (s or "").strip().casefold()


@dataclass
class TargetGeo:
    """Regole di filtro geografico e di tipologia, pronte per lo scraper."""

    # Nomi provincia (normalizzati) prese per intero: qualsiasi comune va bene.
    province_intere: set[str] = field(default_factory=set)
    # Coppie (provincia_norm, comune_norm) ammesse fuori dalle province intere.
    comuni_ammessi: set[tuple[str, str]] = field(default_factory=set)
    solo_residenziale: bool = True

    def ammette(self, provincia: str | None, comune: str | None) -> bool:
        """True se un immobile in quella provincia/comune rientra nel target."""
        p = _norm(provincia)
        if p in self.province_intere:
            return True
        return (p, _norm(comune)) in self.comuni_ammessi


def carica_target(path: str | Path = "config/comuni.yaml") -> TargetGeo:
    dati = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    geo = dati.get("geografia", {}) or {}

    province_intere: set[str] = set()
    for prov in geo.get("province", []) or []:
        if not prov.get("attivo"):
            continue
        nome = prov.get("nome") or SIGLA_PROVINCIA.get(prov.get("sigla", ""), "")
        if nome:
            province_intere.add(_norm(nome))

    comuni_ammessi: set[tuple[str, str]] = set()
    for com in geo.get("comuni_extra", []) or []:
        if not com.get("attivo"):
            continue
        prov_nome = SIGLA_PROVINCIA.get(com.get("provincia", ""), com.get("provincia", ""))
        comuni_ammessi.add((_norm(prov_nome), _norm(com.get("nome"))))

    tip = dati.get("tipologie", {}) or {}
    # solo_residenziale True se residenziale è l'unica tipologia attiva.
    attive = {k for k, v in tip.items() if v}
    solo_residenziale = attive == {"residenziale"} if attive else True

    return TargetGeo(
        province_intere=province_intere,
        comuni_ammessi=comuni_ammessi,
        solo_residenziale=solo_residenziale,
    )
