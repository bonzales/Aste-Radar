"""Notifiche Telegram (CLAUDE.md §6, §7). Bot DEDICATO ad aste-radar.

Wrapper sottile sulla Bot API (one-way): la formattazione del messaggio è
deterministica e testata; l'invio HTTP è thin (smoke test, §9.2). Token e chat_id
vengono dai segreti (config/secrets.env), mai hardcodati (§10).
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx

from src.models import Lotto


def leggi_secrets(path: str | Path = "config/secrets.env") -> dict[str, str]:
    """Parser minimale di un file KEY=VALUE. Le variabili d'ambiente hanno
    precedenza (utile sul VPS/cron)."""
    valori: dict[str, str] = {}
    p = Path(path)
    if p.exists():
        for riga in p.read_text(encoding="utf-8").splitlines():
            riga = riga.strip()
            if not riga or riga.startswith("#") or "=" not in riga:
                continue
            chiave, _, valore = riga.partition("=")
            valori[chiave.strip()] = valore.strip()
    valori.update({k: v for k, v in os.environ.items() if k in valori or k.startswith("TELEGRAM_")})
    return valori


def lista_chat_id(valore) -> list[str]:
    """Normalizza il valore di TELEGRAM_CHAT_ID in una lista di id. Ammette un
    singolo id o più id separati da virgola/punto e virgola (per condividere le
    notifiche con più persone)."""
    if valore is None:
        return []
    if isinstance(valore, (list, tuple, set)):
        grezzi = [str(v) for v in valore]
    else:
        grezzi = str(valore).replace(";", ",").split(",")
    return [c.strip() for c in grezzi if c.strip()]


def _euro(v: float | None) -> str | None:
    if v is None:
        return None
    return f"€ {v:,.0f}".replace(",", ".")


def formatta_messaggio(lotto: Lotto) -> str:
    """Messaggio Telegram per un lotto. Le righe con campo assente si omettono
    (mai valori inventati, §1.2)."""
    righe: list[str] = []
    righe.append(f"🏠 {lotto.titolo}" if lotto.titolo else "🏠 Nuovo lotto")
    luogo = " ".join(
        p for p in [lotto.comune, f"({lotto.provincia})" if lotto.provincia else None] if p
    )
    if luogo:
        righe.append(f"📍 {luogo}")
    if lotto.prezzo_base is not None:
        righe.append(f"💶 Base: {_euro(lotto.prezzo_base)}")
    if lotto.data_vendita:
        righe.append(f"🗓 Vendita: {lotto.data_vendita}")
    if lotto.esito_stato == "verifica":
        righe.append(f"⚠️ Promettente, DA VERIFICARE a mano ({lotto.motivazione})")
    elif lotto.motivazione:
        stelle = ""
        if lotto.punteggio is not None:
            n = 1 + round(lotto.punteggio * 4)  # 1..5
            stelle = " " + "★" * n + "☆" * (5 - n)
        righe.append(f"✅ {lotto.motivazione}{stelle}")
    if lotto.url:
        righe.append(f"🔗 {lotto.url}")
    return "\n".join(righe)


class TelegramNotifier:
    """Invio one-way su Telegram tramite Bot API."""

    def __init__(self, token: str, chat_id, http: httpx.Client | None = None):
        self._token = token
        # uno o più destinatari: le notifiche vanno a tutti gli id autorizzati.
        self._chat_ids = lista_chat_id(chat_id)
        self._http = http or httpx.Client(timeout=30.0)

    def _invia(self, testo: str) -> None:
        for chat_id in self._chat_ids:
            resp = self._http.post(
                f"https://api.telegram.org/bot{self._token}/sendMessage",
                json={"chat_id": chat_id, "text": testo, "disable_web_page_preview": True},
            )
            resp.raise_for_status()

    def invia_lotto(self, lotto: Lotto) -> None:
        self._invia(formatta_messaggio(lotto))

    def invia_errore(self, motivo: str) -> None:
        """Fail loud (CLAUDE.md §1.4): segnala una scansione fallita."""
        self._invia(f"⚠️ Scansione aste fallita: {motivo}")

    @classmethod
    def da_secrets(cls, secrets: dict[str, str]) -> "TelegramNotifier":
        token = secrets.get("TELEGRAM_BOT_TOKEN")
        chat_id = secrets.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            raise RuntimeError(
                "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID mancanti in config/secrets.env"
            )
        return cls(token, chat_id)

    def close(self) -> None:
        self._http.close()
