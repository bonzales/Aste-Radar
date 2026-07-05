"""Download degli allegati dei lotti in raw/ (CLAUDE.md §3 Fase 2, §1.1).

Dal dettaglio pubblico del lotto (`/vendite/{id}`) si legge l'elenco `allegati`
(perizia, avviso/ordinanza, altro) e si scaricano i file dal bucket pubblico
`resource-pvp.giustizia.it`.

Principi:
- raw/ è IMMUTABILE (§1.1): un file già presente NON si ri-scarica né si
  sovrascrive. L'operazione è idempotente.
- Nessuna invenzione: si scarica ciò che il portale espone, con il nome originale.

La parte deterministica (parsing allegati, costruzione URL, nome file sicuro) è
testata in TDD; il download HTTP è I/O (integrazione).
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

import httpx

RESOURCE_HOST = "https://resource-pvp.giustizia.it"
USER_AGENT = "aste-radar/0.1 (uso personale; info@chiriba.com)"

# Codici tipo allegato del PVP → etichetta leggibile.
TIPO_ALLEGATO = {
    "PERIZ": "perizia",
    "ORDIN": "ordinanza/avviso",
    "AVVIS": "avviso",
    "ALTRO": "altro",
}


@dataclass
class Allegato:
    id_allegato: str
    nome_file: str
    link: str                 # relativo, es. "/allegati/<id>/<nome>.pdf?versionId=..."
    tipo: str | None = None   # codiceTipoAllegato (PERIZ, ORDIN, ALTRO, ...)
    dimensione: int | None = None

    @property
    def tipo_leggibile(self) -> str:
        return TIPO_ALLEGATO.get(self.tipo or "", (self.tipo or "sconosciuto").lower())

    @property
    def is_perizia(self) -> bool:
        return self.tipo == "PERIZ"


def parse_allegati(dettaglio: dict) -> list[Allegato]:
    """Estrae gli allegati dal JSON di dettaglio del lotto. Scarta le voci senza
    link o id (non scaricabili)."""
    body = dettaglio.get("body", dettaglio) if isinstance(dettaglio, dict) else {}
    out: list[Allegato] = []
    for a in body.get("allegati") or []:
        link = a.get("linkAllegato")
        id_all = a.get("idAllegato")
        if not link or id_all is None:
            continue
        out.append(
            Allegato(
                id_allegato=str(id_all),
                nome_file=a.get("nomeFile") or f"allegato-{id_all}",
                link=link,
                tipo=a.get("codiceTipoAllegato"),
                dimensione=a.get("dimensioneAllegato"),
            )
        )
    return out


def url_download(link: str) -> str:
    """URL assoluto del file sul bucket pubblico, con path correttamente
    codificato (i nomi file contengono spazi e caratteri speciali)."""
    path, _, query = link.partition("?")
    enc = urllib.parse.quote(path)
    return f"{RESOURCE_HOST}{enc}" + (f"?{query}" if query else "")


def nome_file_sicuro(nome: str) -> str:
    """Nome file innocuo per il filesystem (niente separatori di percorso, ecc.)."""
    nome = nome.replace("\x00", "").strip()
    nome = re.sub(r"[/\\]+", "_", nome)
    nome = re.sub(r"[^\w.\- ()]+", "_", nome, flags=re.UNICODE).strip(" .")
    return (nome or "allegato")[:180]


def scarica_allegati(
    client,
    lotto,
    dir_base: str | Path = "raw",
    data: str | None = None,
    http: httpx.Client | None = None,
) -> list[Path]:
    """Scarica gli allegati del lotto in raw/<data>/<id_lotto>/ e ritorna i
    percorsi salvati. Idempotente: i file già presenti (stessa dimensione) non si
    ri-scaricano. `data` = cartella per data (default: prima_vista o oggi)."""
    from datetime import date

    chiudi = http is None
    http = http or httpx.Client(
        timeout=120.0, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    )
    try:
        data = data or (lotto.prima_vista_il or date.today().isoformat())[:10]
        dest = Path(dir_base) / data / str(lotto.id_esterno)
        dest.mkdir(parents=True, exist_ok=True)

        dettaglio = client.dettaglio_vendita(lotto.id_esterno)
        salvati: list[Path] = []
        for al in parse_allegati(dettaglio):
            target = dest / nome_file_sicuro(al.nome_file)
            # idempotenza: non sovrascrivere raw/ se il file è già completo
            if target.exists() and al.dimensione and target.stat().st_size == al.dimensione:
                salvati.append(target)
                continue
            _scarica_stream(http, url_download(al.link), target)
            salvati.append(target)
        return salvati
    finally:
        if chiudi:
            http.close()


def _scarica_stream(http: httpx.Client, url: str, target: Path) -> None:
    """Scarica su file temporaneo e rinomina a fine (nessun file parziale in raw/)."""
    tmp = target.with_suffix(target.suffix + ".part")
    with http.stream("GET", url) as resp:
        resp.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in resp.iter_bytes(chunk_size=65536):
                f.write(chunk)
    tmp.replace(target)
