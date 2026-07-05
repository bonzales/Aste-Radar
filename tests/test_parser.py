"""Test dell'estrazione testo/OCR (Fase 2/3).

- Il caso "PDF digitale" è testato in modo veloce e deterministico creando al volo
  un PDF con testo (nessun OCR, nessun binario esterno).
- Il caso OCR reale è un test d'integrazione sulla perizia campione: si salta se
  il file campione o Tesseract non sono presenti (così la suite resta verde
  ovunque, §9.2).
"""

import shutil
from pathlib import Path

import pytest

import fitz

from src.parser import _pagina_ha_testo, estrai_testo

PERIZIA = Path("raw/2026-07-05/4604105/perizia_con_allegati_venezia (1).pdf")


def test_pagina_ha_testo_soglia():
    assert _pagina_ha_testo("Valore di stima 100.000 euro") is True
    assert _pagina_ha_testo("   ") is False
    assert _pagina_ha_testo("x") is False


def test_pdf_digitale_estratto_senza_ocr(tmp_path):
    pdf = tmp_path / "digitale.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PERIZIA\nValore di stima: 123456 euro\nSuperficie 80 mq")
    doc.save(pdf)
    doc.close()

    res = estrai_testo(pdf)
    assert res.metodo == "digitale"
    assert res.n_pagine_ocr == 0
    assert "Valore di stima" in res.testo
    assert "123456" in res.testo


@pytest.mark.skipif(
    not PERIZIA.exists() or shutil.which("tesseract") is None,
    reason="perizia campione o Tesseract non disponibili",
)
def test_ocr_su_perizia_scansionata_reale():
    # solo le prime pagine per tenere il test rapido
    res = estrai_testo(PERIZIA, max_pagine=3)
    assert res.n_pagine_ocr >= 1
    assert res.metodo in ("ocr", "misto")
    # l'OCR italiano deve produrre testo sensato
    assert len(res.testo) > 100
