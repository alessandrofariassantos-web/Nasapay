# utils/ui_envio/pdftext.py
# Extração de texto do PDF com fallback para OCR (opcional)
import os

def extract_text(path:str) -> str:
    txt = ""
    # 1) PyPDF2
    try:
        from PyPDF2 import PdfReader
        r = PdfReader(path)
        for p in r.pages[:4]:
            t = p.extract_text() or ""
            if t: txt += "\n" + t
        if txt.strip(): return txt
    except Exception:
        pass
    # 2) pdfminer.six
    try:
        from pdfminer.high_level import extract_text as pm_extract
        txt = pm_extract(path) or ""
        if txt.strip(): return txt
    except Exception:
        pass
    # 3) OCR (primeira página)
    try:
        import pytesseract
        from pdf2image import convert_from_path
        imgs = convert_from_path(path, first_page=1, last_page=1)
        if imgs:
            txt = pytesseract.image_to_string(imgs[0]) or ""
            return txt
    except Exception:
        pass
    return ""
