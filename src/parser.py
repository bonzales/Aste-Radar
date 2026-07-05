"""Estrazione del testo dalle perizie (CLAUDE.md §3 Fase 2/3, §7).

Molte perizie sono PDF digitali (hanno un layer di testo), ma molte altre sono
SCANSIONI (solo immagini) → serve l'OCR. Questo modulo decide pagina per pagina:
- se la pagina ha testo nativo, lo usa (veloce e affidabile);
- altrimenti la rende come immagine e la passa a Tesseract (OCR, lingua italiana).

Pipeline OCR: PyMuPDF rende la pagina a immagine (equivalente a pdftoppm) →
Tesseract (CLAUDE.md §7). Il testo grezzo estratto alimenta poi extractor.py.
Nessun dato viene interpretato qui: si estrae solo il testo.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

# Sotto questa soglia di caratteri "veri" una pagina è considerata da OCR.
SOGLIA_TESTO_PAGINA = 20


@dataclass
class TestoEstratto:
    testo: str
    n_pagine: int
    n_pagine_ocr: int
    metodo: str  # "digitale" | "ocr" | "misto" | "vuoto"


def _pagina_ha_testo(testo: str, soglia: int = SOGLIA_TESTO_PAGINA) -> bool:
    return len(testo.strip()) >= soglia


def _ocr_immagine(png_bytes: bytes, lingua: str) -> str:
    import pytesseract
    from PIL import Image

    with Image.open(io.BytesIO(png_bytes)) as img:
        return pytesseract.image_to_string(img, lang=lingua)


def estrai_testo(
    pdf_path: str | Path,
    lingua: str = "ita",
    dpi: int = 300,
    ocr: bool = True,
    max_pagine: int | None = None,
) -> TestoEstratto:
    """Estrae il testo dal PDF, con OCR sulle pagine scansionate.

    `max_pagine` limita le pagine elaborate (utile per test/anteprima). `ocr=False`
    disabilita l'OCR (solo testo nativo).
    """
    parti: list[str] = []
    n_ocr = 0
    usato_nativo = False

    with fitz.open(pdf_path) as doc:
        n_tot = doc.page_count
        limite = min(n_tot, max_pagine) if max_pagine else n_tot
        for i in range(limite):
            pagina = doc[i]
            nativo = pagina.get_text()
            if _pagina_ha_testo(nativo):
                parti.append(nativo)
                usato_nativo = True
            elif ocr:
                png = pagina.get_pixmap(dpi=dpi).tobytes("png")
                testo_ocr = _ocr_immagine(png, lingua)
                parti.append(testo_ocr)
                if _pagina_ha_testo(testo_ocr):
                    n_ocr += 1

    testo = "\n\n".join(parti).strip()
    if not testo:
        metodo = "vuoto"
    elif n_ocr and usato_nativo:
        metodo = "misto"
    elif n_ocr:
        metodo = "ocr"
    else:
        metodo = "digitale"
    return TestoEstratto(testo=testo, n_pagine=limite, n_pagine_ocr=n_ocr, metodo=metodo)
