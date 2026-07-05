"""Scraper del Portale Vendite Pubbliche (CLAUDE.md §8, research/pvp-api.md).

Il PVP è una SPA che espone i dati via API JSON. Qui:
- `parse_risposta_ricerca` / `filtra_lotti`: logica DETERMINISTICA (mapping +
  filtro geografico/tipologia) → testata in TDD sulle fixture reali.
- `PvpClient`: I/O HTTP verso l'API, con auto-discovery degli URL (che
  contengono un hash di deploy) per non rompersi ad ogni rilascio del portale.
- `scansiona`: orchestrazione — pagina i lotti più recenti e li filtra.

Strategia geografica (vedi research/pvp-api.md): si pagina l'elenco immobili
ordinato per data di pubblicazione decrescente e si filtra LATO CLIENT per
provincia/comune. Non si usa la ricerca testuale del portale perché è sporca
(es. "Mogliano Veneto" pesca anche Mogliano in provincia di Macerata).
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import httpx

from src.config import TargetGeo
from src.models import Lotto

# --- Endpoint noti (default dallo spike 2026-07-05); l'hash può cambiare, per
#     questo PvpClient prova a riscoprirli a runtime da fe-config. ---
HOST = "https://pvp.giustizia.it"
HOME_URL = f"{HOST}/pvp/"
BASE_RICERCA_DEFAULT = f"{HOST}/ric-496b258c-986a1b71/ric-ms"
FE_CONFIG_BO_DEFAULT = "/bo-5897bc47-986a1b71/bo-ms"
DETTAGLIO_URL = f"{HOST}/pvp/it/detail_annuncio.page?idAnnuncio={{id}}"

CATEGORIA_RESIDENZIALE = "IMMOBILE_RESIDENZIALE"
USER_AGENT = "aste-radar/0.1 (uso personale; info@chiriba.com)"


def _body(data: dict) -> dict:
    """La risposta è talvolta {"body": {...}} e talvolta già il body."""
    return data.get("body", data) if isinstance(data, dict) else {}


def parse_risposta_ricerca(data: dict) -> list[Lotto]:
    """Mappa la risposta JSON dell'API in oggetti Lotto. Nessuna invenzione:
    campi assenti restano None (CLAUDE.md §1.2). I lotti senza `id` si scartano
    (senza id non c'è deduplica possibile)."""
    lotti: list[Lotto] = []
    for it in _body(data).get("content", []) or []:
        if it.get("id") is None:
            continue
        ind = it.get("indirizzo") or {}
        lotti.append(
            Lotto(
                fonte="pvp",
                id_esterno=str(it["id"]),
                url=DETTAGLIO_URL.format(id=it["id"]),
                comune=ind.get("citta"),
                provincia=ind.get("provincia"),
                titolo=it.get("descLotto"),
                prezzo_base=it.get("prezzoBaseAsta"),
                data_vendita=it.get("dataVendita"),
                categoria=it.get("categoriaLotto"),
                data_pubblicazione=it.get("dataPubblicazione"),
            )
        )
    return lotti


def filtra_lotti(lotti: list[Lotto], target: TargetGeo) -> list[Lotto]:
    """Tiene solo i lotti nell'area target (provincia/comune) e — se richiesto —
    solo i residenziali. È il filtro che disinnesca i falsi positivi della fonte."""
    out = []
    for l in lotti:
        if not target.ammette(l.provincia, l.comune):
            continue
        if target.solo_residenziale and l.categoria != CATEGORIA_RESIDENZIALE:
            continue
        out.append(l)
    return out


class PvpClient:
    """Client HTTP verso l'API del PVP. Thin wrapper: l'I/O sta qui, la logica no."""

    def __init__(self, http: httpx.Client | None = None, base_ricerca: str | None = None):
        self._http = http or httpx.Client(
            timeout=30.0, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
        )
        self.base_ricerca = base_ricerca or BASE_RICERCA_DEFAULT

    def scopri_config(self) -> None:
        """Aggiorna base_ricerca leggendo la config runtime del portale (fe-config).
        Best-effort: se qualcosa va storto, resta il default. Così un cambio di
        hash degli URL non rompe lo scraper senza intervento umano."""
        try:
            home = self._http.get(HOME_URL).text
            m = re.search(r'bo-ms&quot;:\{&quot;url&quot;:&quot;([^&]+)&quot;', home)
            bo = m.group(1) if m else FE_CONFIG_BO_DEFAULT
            cfg = self._http.get(f"{HOST}{bo}/fe-config/it").json()
            cfg = cfg.get("body", cfg)
            host = cfg.get("host", HOST)
            ricerca = (cfg.get("msUrl") or {}).get("ricerca")
            if ricerca:
                self.base_ricerca = f"{host}/{ricerca}"
        except Exception:
            pass  # fail soft: teniamo il default

    def cerca(self, page: int, size: int, sort: str = "dataPubblicazione,desc") -> dict:
        """Una pagina di risultati (immobili) ordinati per pubblicazione desc."""
        resp = self._http.post(
            f"{self.base_ricerca}/ricerca/vendite",
            params={"page": page, "size": size, "sort": sort},
            json={"tipoLotto": "IMMOBILI"},
        )
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        self._http.close()


def scansiona(
    client: PvpClient,
    target: TargetGeo,
    giorni_indietro: int = 7,
    size: int = 100,
    max_pagine: int = 40,
    oggi: date | None = None,
) -> list[Lotto]:
    """Scorre i lotti pubblicati di recente e ritorna quelli nell'area target,
    deduplicati per id. Si ferma quando la pagina scende sotto l'orizzonte
    temporale (`giorni_indietro`) o non ci sono più pagine."""
    cutoff = ((oggi or date.today()) - timedelta(days=giorni_indietro)).isoformat()
    trovati: dict[str, Lotto] = {}
    for page in range(max_pagine):
        data = client.cerca(page, size)
        lotti = parse_risposta_ricerca(data)
        if not lotti:
            break
        for l in filtra_lotti(lotti, target):
            trovati[l.id_esterno] = l
        pubblicazioni = [l.data_pubblicazione for l in lotti if l.data_pubblicazione]
        if pubblicazioni and min(pubblicazioni) < cutoff:
            break
        if _body(data).get("last"):
            break
    return list(trovati.values())
