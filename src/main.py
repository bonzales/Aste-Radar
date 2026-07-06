"""Orchestratore del ciclo (CLAUDE.md §3, §4, §5) — funnel a livelli.

Livello 0/1 (gratis): scansiona TUTTI gli immobili nella finestra, tieni solo
  quelli dell'area target, residenziali, entro budget, con vendita futura.
Livello 2 (~cent): per ogni lotto NON ancora analizzato, scarica gli allegati,
  OCR della perizia, estrazione IA, punteggio con la griglia. Una volta sola.
Notifica: solo i lotti che PASSANO la griglia (§5), col dettaglio.

Idempotente (rilanciare non duplica né ri-analizza né re-notifica) e fail loud
(su errore avvisa Telegram, exit != 0). Uso: python -m src.main
"""

from __future__ import annotations

import sys
from datetime import date, datetime

import anthropic
from pydantic import ValidationError

from src import db
from src.config import carica_target
from src.downloader import parse_allegati, scarica_allegati
from src.extractor import PeriziaEstratta, estrai_perizia, verifica_ai
from src.flip import calcola_margine, flip_abilitato
from src.notifier import TelegramNotifier, leggi_secrets
from src.parser import estrai_testo
from src.scorer import Esito, carica_griglia, valuta
from src.scraper import PvpClient, scansiona

DB_PATH = "db/aste.sqlite"
GIORNI_SETTIMANALE = 14     # giro settimanale: 14 gg coprono il gap con margine
GIORNI_BACKFILL = 180       # primo giro (DB vuoto): recupera l'arretrato aperto
MAX_PAGINE_OCR = 80         # profondità OCR per perizia (analisi accurata, §utente)


def _analizza_lotto(lotto, client, ai_client, griglia, dir_raw, max_pagine_ocr) -> Esito:
    """Livello 2 su un singolo lotto: allegati -> OCR perizia -> IA -> griglia."""
    dettaglio = client.dettaglio_vendita(lotto.id_esterno)
    allegati = parse_allegati(dettaglio)
    perizie = [a for a in allegati if a.is_perizia]
    if not perizie:
        return Esito(passa=False, sconto=None, punteggio=None,
                     da_verificare=["perizia non disponibile"])

    salvati = scarica_allegati(client, lotto, dir_base=dir_raw)
    from src.downloader import nome_file_sicuro
    atteso = nome_file_sicuro(perizie[0].nome_file)
    perizia_path = next((p for p in salvati if p.name == atteso), None)
    if perizia_path is None:
        return Esito(passa=False, sconto=None, punteggio=None,
                     da_verificare=["perizia non scaricata"])

    testo = estrai_testo(perizia_path, max_pagine=max_pagine_ocr)
    if testo.metodo == "vuoto":
        return Esito(passa=False, sconto=None, punteggio=None,
                     da_verificare=["perizia illeggibile"])

    try:
        dati: PeriziaEstratta = estrai_perizia(ai_client, testo.testo)
    except (ValueError, ValidationError):
        # Perizia illeggibile dal modello (JSON non valido anche dopo escalation).
        # NON perdere il lotto e NON ritentarlo all'infinito (§ non perdere
        # occasioni): segnalalo per lettura manuale. Diverso da un errore di rete,
        # che invece propaga e viene ri-tentato al giro dopo.
        return Esito(passa=False, sconto=None, punteggio=None,
                     da_verificare=["perizia non interpretabile dal modello — leggere a mano"])
    esito = valuta(lotto, dati, griglia)

    # Livello 3: se abilitato e il lotto è interessante (passa/verifica), stima il
    # margine di flip e aggiungilo alla motivazione mostrata nella notifica.
    if flip_abilitato(griglia) and esito.codice() in (1, 2):
        margine = calcola_margine(lotto.prezzo_base, dati.valore_stima,
                                  dati.superficie_mq, griglia)
        if margine is not None:
            esito.motivazioni.append(margine.riga())
    return esito


def esegui(client, ai_client, notifier, conn, target, griglia, *,
           giorni_indietro, prezzo_max, dir_raw="raw",
           max_pagine_ocr=MAX_PAGINE_OCR, now=None):
    """Nucleo testabile del run (funnel completo). Ritorna le statistiche."""
    now = now or datetime.now().isoformat(timespec="seconds")

    # Livello 0/1: scansione completa della finestra + filtro area/budget/futuro
    print(f"[aste-radar] scansione finestra {giorni_indietro}gg...", flush=True)
    lotti = scansiona(client, target, giorni_indietro=giorni_indietro, prezzo_max=prezzo_max)
    nuovi = sum(1 for l in lotti if db.upsert_lotto(conn, l, now))

    # Livello 2: analizza (una volta) i lotti non ancora analizzati
    da_analizzare = db.lotti_da_analizzare(conn)
    print(f"[aste-radar] trovati {len(lotti)} in zona; {len(da_analizzare)} da analizzare "
          f"(perizia + IA, qualche minuto ciascuno)...", flush=True)
    analizzati = errori = 0
    for i, lotto in enumerate(da_analizzare, 1):
        try:
            esito = _analizza_lotto(lotto, client, ai_client, griglia, dir_raw, max_pagine_ocr)
        except Exception as exc:  # errore transitorio: lascia da ri-analizzare
            errori += 1
            print(f"[aste-radar] [{i}/{len(da_analizzare)}] {lotto.comune} "
                  f"{lotto.id_esterno}: ERRORE {exc}", file=sys.stderr, flush=True)
            continue
        db.segna_analizzato(conn, lotto.id, now, esito.codice(), esito.punteggio,
                            esito.riassunto())
        analizzati += 1
        print(f"[aste-radar] [{i}/{len(da_analizzare)}] {lotto.comune} "
              f"{lotto.id_esterno}: {esito.stato().upper()} — {esito.riassunto()[:90]}", flush=True)

    # Notifica: solo i promossi non ancora notificati
    notificati = 0
    for lotto in db.lotti_da_notificare(conn):
        notifier.invia_lotto(lotto)
        db.segna_notificato(conn, lotto.id, now)
        notificati += 1

    # Fail loud (§1.4): se OGNI analisi tentata è fallita, è un problema sistemico
    # (chiave IA errata, rete, portale) — non fingere che "non ci fosse nulla".
    if errori and not analizzati:
        raise RuntimeError(
            f"analisi fallita su tutti i {errori} lotti da analizzare "
            f"(possibile chiave IA errata o problema di rete)"
        )

    return {"trovati": len(lotti), "nuovi": nuovi, "analizzati": analizzati,
            "errori_analisi": errori, "notificati": notificati}


def main() -> int:
    notifier = None
    try:
        secrets = leggi_secrets()
        target = carica_target()
        griglia = carica_griglia()
        prezzo_max = (griglia.get("hard") or {}).get("prezzo_base_max")

        notifier = TelegramNotifier.da_secrets(secrets)

        # Preflight della chiave IA: falla SUBITO (in secondi) se la chiave è
        # assente/errata, invece di scoprirlo perizia per perizia dopo ore di OCR.
        # Una chiave incollata a mano può contenere trattini "lunghi" (–, non-ASCII)
        # al posto di "-": l'httpx della SDK non può metterla nell'header. La
        # intercettiamo con un messaggio chiaro invece dell'oscuro UnicodeEncodeError.
        chiave = secrets.get("ANTHROPIC_API_KEY") or ""
        if not chiave:
            raise RuntimeError("ANTHROPIC_API_KEY mancante in config/secrets.env")
        if not chiave.isascii():
            raise RuntimeError(
                "ANTHROPIC_API_KEY contiene caratteri non-ASCII (probabile "
                "trattino 'lungo' da copia-incolla): riscrivi la chiave a mano"
            )
        ai_client = anthropic.Anthropic(api_key=chiave)
        try:
            verifica_ai(ai_client)
        except Exception as exc:
            raise RuntimeError(f"chiave IA non valida o IA irraggiungibile: {exc}") from exc

        conn = db.connect(DB_PATH)
        db.init_db(conn)
        # primo giro (DB vuoto) = backfill ampio; poi finestra settimanale
        vuoto = conn.execute("SELECT COUNT(*) FROM lotti").fetchone()[0] == 0
        giorni = GIORNI_BACKFILL if vuoto else GIORNI_SETTIMANALE

        client = PvpClient()
        client.scopri_config()

        stats = esegui(client, ai_client, notifier, conn, target, griglia,
                       giorni_indietro=giorni, prezzo_max=prezzo_max)
        client.close()
        conn.close()
        print(
            f"[aste-radar] finestra={giorni}gg trovati={stats['trovati']} "
            f"nuovi={stats['nuovi']} analizzati={stats['analizzati']} "
            f"errori={stats['errori_analisi']} notificati={stats['notificati']}"
        )
        return 0
    except Exception as exc:  # fail loud (CLAUDE.md §1.4)
        motivo = f"{type(exc).__name__}: {exc}"
        print(f"[aste-radar] ERRORE: {motivo}", file=sys.stderr)
        if notifier is not None:
            try:
                notifier.invia_errore(motivo)
            except Exception as exc2:
                print(f"[aste-radar] impossibile avvisare su Telegram: {exc2}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
