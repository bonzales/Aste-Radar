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
BASE_VENDITE_DEFAULT = f"{HOST}/ve-3f723b85-986a1b71/ve-ms"
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


def filtra_lotti(
    lotti: list[Lotto],
    target: TargetGeo,
    prezzo_max: float | None = None,
    solo_future: bool = False,
    oggi: "date | None" = None,
) -> list[Lotto]:
    """Filtro di LIVELLO 1 (gratis, solo dati della ricerca): tiene i lotti
    nell'area target, residenziali, entro il tetto di prezzo e — se richiesto —
    con vendita ancora da tenere. È il filtro che disinnesca i falsi positivi
    della fonte PRIMA di spendere in download/OCR/IA."""
    oggi_iso = (oggi or date.today()).isoformat()
    out = []
    for l in lotti:
        if not target.ammette(l.provincia, l.comune):
            continue
        if target.solo_residenziale and l.categoria != CATEGORIA_RESIDENZIALE:
            continue
        if prezzo_max is not None and l.prezzo_base is not None and l.prezzo_base > prezzo_max:
            continue
        # solo aste aperte: data vendita futura (se nota); se ignota, si tiene
        if solo_future and l.data_vendita and l.data_vendita < oggi_iso:
            continue
        out.append(l)
    return out


class PvpClient:
    """Client HTTP verso l'API del PVP. Thin wrapper: l'I/O sta qui, la logica no."""

    def __init__(
        self,
        http: httpx.Client | None = None,
        base_ricerca: str | None = None,
        base_vendite: str | None = None,
    ):
        self._http = http or httpx.Client(
            timeout=30.0, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
        )
        self.base_ricerca = base_ricerca or BASE_RICERCA_DEFAULT
        self.base_vendite = base_vendite or BASE_VENDITE_DEFAULT

    def scopri_config(self) -> None:
        """Aggiorna le basi degli URL leggendo la config runtime (fe-config).
        Best-effort: se qualcosa va storto, restano i default. Così un cambio di
        hash degli URL non rompe lo scraper senza intervento umano."""
        try:
            home = self._http.get(HOME_URL).text
            m = re.search(r'bo-ms&quot;:\{&quot;url&quot;:&quot;([^&]+)&quot;', home)
            bo = m.group(1) if m else FE_CONFIG_BO_DEFAULT
            cfg = self._http.get(f"{HOST}{bo}/fe-config/it").json()
            cfg = cfg.get("body", cfg)
            host = cfg.get("host", HOST)
            ms = cfg.get("msUrl") or {}
            if ms.get("ricerca"):
                self.base_ricerca = f"{host}/{ms['ricerca']}"
            if ms.get("vendite"):
                self.base_vendite = f"{host}/{ms['vendite']}"
        except Exception:
            pass  # fail soft: teniamo i default

    def dettaglio_vendita(self, id_lotto: str | int) -> dict:
        """Dettaglio pubblico di un lotto (include l'elenco `allegati`)."""
        resp = self._http.get(f"{self.base_vendite}/vendite/{id_lotto}")
        resp.raise_for_status()
        return resp.json()

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
    giorni_indietro: int = 14,
    size: int = 200,
    prezzo_max: float | None = None,
    solo_future: bool = True,
    max_pagine: int = 2000,
    oggi: date | None = None,
) -> list[Lotto]:
    """Scorre TUTTI gli immobili pubblicati nella finestra `giorni_indietro`
    (ordinati per data di pubblicazione decrescente) e ritorna quelli dell'area
    target, deduplicati per id. COMPLETEZZA: non c'è un tetto basso di pagine —
    si scorre finché la finestra non è coperta. `max_pagine` è solo una valvola
    di sicurezza; se scatta, la copertura è incompleta (lo segnala chi chiama).

    `giorni_indietro`: usa un valore ampio al primo giro (backfill, es. 180) e
    ridotto a regime (es. 14 per un giro settimanale, con margine sul gap).
    """
    cutoff = ((oggi or date.today()) - timedelta(days=giorni_indietro)).isoformat()
    trovati: dict[str, Lotto] = {}
    completa = False
    for page in range(max_pagine):
        data = client.cerca(page, size)
        lotti = parse_risposta_ricerca(data)
        if not lotti:
            completa = True
            break
        for l in filtra_lotti(lotti, target, prezzo_max=prezzo_max,
                              solo_future=solo_future, oggi=oggi):
            trovati[l.id_esterno] = l
        pubblicazioni = [l.data_pubblicazione for l in lotti if l.data_pubblicazione]
        if pubblicazioni and min(pubblicazioni) < cutoff:
            completa = True
            break
        if _body(data).get("last"):
            completa = True
            break
    if not completa:
        # valvola di sicurezza scattata: la finestra non è stata coperta del tutto
        raise CoperturaIncompleta(
            f"raggiunto il tetto di {max_pagine} pagine senza coprire la finestra "
            f"di {giorni_indietro} giorni: possibili lotti non visti"
        )
    return list(trovati.values())


class CoperturaIncompleta(RuntimeError):
    """La scansione non ha coperto l'intera finestra temporale (valvola di
    sicurezza): fail loud, non fingere completezza (CLAUDE.md §1.4)."""
