"""Modello dati dei lotti (Fase 1).

Solo i campi della notifica grezza (CLAUDE.md §3, §4 Fase 1). Le fasi successive
aggiungeranno i campi estratti dalla perizia (valore_stima, superficie, ecc.).

Principio §1.2: un campo non disponibile resta `None`, mai inventato.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Lotto:
    """Un lotto d'asta come visto dallo scraper, prima di ogni analisi.

    `id` è la chiave di riga del DB (None finché non persistito). La chiave di
    identità logica per l'idempotenza è invece la coppia (`fonte`, `id_esterno`).
    """

    fonte: str
    id_esterno: str
    url: str
    comune: str | None = None
    provincia: str | None = None
    titolo: str | None = None
    prezzo_base: float | None = None
    data_vendita: str | None = None  # ISO date, se disponibile
    raw_path: str | None = None      # percorso dell'HTML grezzo in raw/
    # Transitori: usati dallo scraper per filtrare e per la logica "nuovi",
    # NON persistiti nel DB di Fase 1 (tornano None se riletti dal DB).
    categoria: str | None = None          # es. "IMMOBILE_RESIDENZIALE"
    data_pubblicazione: str | None = None  # ISO date
    # Popolati dal DB, non dallo scraper:
    id: int | None = None
    prima_vista_il: str | None = None
    notificato_il: str | None = None
