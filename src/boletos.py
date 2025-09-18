# src/boletos.py
import os
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from utils import store

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

try:
    from reportlab.graphics.barcode.interleaved2of5 import Interleaved2of5 as I25
except Exception:
    try:
        from reportlab.graphics.barcode.i2of5 import Interleaved2of5 as I25
    except Exception:
        I25 = None

from src.extrator_titulos import extrair_titulos_de_arquivo
from utils.parametros import carregar_parametros
from utils.boletos_bmp import (
    montar_codigo_barras,
    montar_linha_digitavel,
    dv_nosso_numero_base7,
)

# ---------------- helpers ----------------

def draw_logo_fit(c, path, x, y, max_w, max_h):
    try:
        img = ImageReader(path)
        iw, ih = img.getSize()
        if iw == 0 or ih == 0:
            return False
        ratio = min(max_w / iw, max_h / ih)
        c.drawImage(img, x, y, width=iw * ratio, height=ih * ratio, mask="auto")
        return True
    except Exception:
        return False

def draw_i25(c, digits, x, y, barWidth=0.33 * mm, barHeight=13 * mm, quiet_zone=5 * mm, ratio=2.2):
    patt = {'0':'nnwwn','1':'wnnnw','2':'nwnnw','3':'wwnnn','4':'nnwnw','5':'wnwnn','6':'nwwnn','7':'nnnww','8':'wnnwn','9':'nwnwn'}
    def w(ch): return 1 if ch=='n' else ratio
    if len(digits) % 2 == 1: digits = '0' + digits
    cursor = x + quiet_zone
    seq = [('bar', w('n')), ('sp', w('n')), ('bar', w('n')), ('sp', w('n'))]
    for i in range(0, len(digits), 2):
        a,b = digits[i],digits[i+1]; pa,pb = patt[a],patt[b]
        for k in range(5):
            seq.append(('bar', w(pa[k]))); seq.append(('sp', w(pb[k])))
    seq.extend([('bar', w('w')), ('sp', w('n')), ('bar', w('n'))])
    for kind, units in seq:
        bw = units * barWidth
        if kind == 'bar':
            c.rect(cursor, y, bw, barHeight, stroke=0, fill=1)
        cursor += bw
    return cursor + quiet_zone

def format_valor_brl(valor_str: str) -> str:
    s = (valor_str or "").strip().replace(" ", "")
    try:
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        v = float(s)
    except Exception:
        v = 0.0
    txt = f"{v:,.2f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")

def _parse_brl_to_float(valor_str: str) -> float:
    s = (valor_str or "").strip().replace(" ", "")
    if s == "":
        return 0.0
    try:
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        d = "".join(ch for ch in s if ch.isdigit())
        if not d:
            return 0.0
        try:
            return float(int(d)) / 100.0
        except Exception:
            return 0.0

def _parse_pct_to_float(pct_str: str) -> float:
    s = (pct_str or "").strip()
    if not s:
        return 0.0
    try:
        if "," in s and "." in s:
            s = s.replace(".", "").replace(",", ".")
        elif "," in s:
            s = s.replace(",", ".")
        return float(s)
    except Exception:
        return 0.0

def _fmt_cpf(d: str) -> str:
    d = "".join(ch for ch in (d or "") if ch.isdigit())[-11:].rjust(11, "0")
    return f"{d[0:3]}.{d[3:6]}.{d[6:9]}-{d[9:11]}"

def _fmt_cnpj(d: str) -> str:
    d = "".join(ch for ch in (d or "") if ch.isdigit())[-14:].rjust(14, "0")
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"

def format_doc_pagador(titulo: dict) -> str:
    """
    Decide entre CPF e CNPJ para o pagador:
      - Usa 'doc_pagador_tipo' se existir ('01' = CPF, '02' = CNPJ)
      - Caso contrário:
          * 11 dígitos => CPF
          * 14 dígitos => se começar com zeros (CPF preenchido) => CPF; senão CNPJ
    """
    tipo = (titulo.get("doc_pagador_tipo") or "").strip()
    raw  = "".join(ch for ch in (titulo.get("sacado_cnpj") or "") if ch.isdigit())

    if tipo == "01":  # CPF
        return _fmt_cpf(raw)
    if tipo == "02":  # CNPJ
        return _fmt_cnpj(raw)

    if len(raw) == 11:
        return _fmt_cpf(raw)
    if len(raw) == 14:
        if raw.startswith(("00000", "0000", "000")):
            return _fmt_cpf(raw[-11:])  # CPF com zeros à esquerda
        return _fmt_cnpj(raw)
    return raw or ""

def format_doc(doc: str) -> str:
    d = "".join(ch for ch in (doc or "") if ch.isdigit())
    if len(d) == 11:
        return _fmt_cpf(d)
    if len(d) == 14:
        return _fmt_cnpj(d)
    return doc or ""

def pad_left(txt: str) -> str:
    return ("   " + (txt or "")).rstrip()

def _unique_sequencial(path):
    base, ext = os.path.splitext(path)
    cand = path
    idx = 2
    while os.path.exists(cand):
        cand = f"{base} - {idx:02d}{ext}"
        idx += 1
    return cand

def _popup_boletos_gerados(arquivos_pdf: list[str], parent=None):
    top = tk.Toplevel(parent) if parent else tk.Toplevel()
    top.title("Boletos Gerados")
    try:
        if parent:
            top.transient(parent)
        top.grab_set(); top.lift(); top.focus_force()
        top.attributes("-topmost", True); top.after(200, lambda: top.attributes("-topmost", False))
    except Exception:
        pass

    total = len(arquivos_pdf)
    pasta = os.path.dirname(arquivos_pdf[0]) if arquivos_pdf else ""
    nomes = [os.path.basename(p) for p in arquivos_pdf]

    frame = ttk.Frame(top); frame.pack(fill="both", expand=True, padx=16, pady=12)

    ttk.Label(frame, text=f"Quantidade de Títulos Gerados: {total:03d}", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0,6))
    ttk.Label(frame, text=("Nome do Boleto Gerado:" if total == 1 else "Nomes dos Boletos Gerados:"), font=("Segoe UI", 10)).pack(anchor="w")

    altura = min(320, 24 * max(3, len(nomes)))
    canvas_w = 720
    canvas = tk.Canvas(frame, width=canvas_w, height=altura, highlightthickness=0)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner_id = canvas.create_window((0,0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set)

    def _on_cfg(_=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
        try:
            max_w = max((lbl.winfo_reqwidth() for lbl in inner.winfo_children()), default=canvas_w)
            canvas.configure(width=min(max_w + 16, 1000))
        except Exception:
            pass
    inner.bind("<Configure>", _on_cfg)

    for nm in nomes:
        ttk.Label(inner, text="• " + nm).pack(anchor="w")

    canvas.pack(side="left", fill="both", expand=True, pady=(2,2))
    scroll.pack(side="left", fill="y")

    ttk.Label(frame, text=f"Local: {pasta}", foreground="#444").pack(anchor="w", pady=(8,0))

    btns = ttk.Frame(frame); btns.pack(anchor="e", pady=(12,0))
    def abrir_local():
        try: os.startfile(pasta)
        except Exception as e: messagebox.showerror("Erro", f"Não consegui abrir a pasta:\n{e}", parent=top)
    ttk.Button(btns, text="Abrir Local do Arquivo", command=abrir_local).pack(side="left", padx=6)
    ttk.Button(btns, text="OK", command=top.destroy).pack(side="left", padx=6)

# --------------- desenho do PDF ---------------

def gerar_boleto_titulos(titulo):
    largura, altura = A4
    p = carregar_parametros()

    # dados do título
    nosso_numero = titulo.get("nosso_numero", "")
    numero_documento = titulo.get("documento", "")
    vencimento = titulo.get("vencimento", "")
    valor_fmt = format_valor_brl(titulo.get("valor", "0,00"))
    valor_float = _parse_brl_to_float(titulo.get("valor", "0,00"))
    sacado = titulo.get("sacado", "")
    endereco = titulo.get("sacado_endereco", "")
    cidade = titulo.get("sacado_cidade", "")
    uf = titulo.get("sacado_uf", "")
    cep = titulo.get("sacado_cep", "")
    emissao = titulo.get("emissao", "")

    # >>> AQUI: usa o tipo quando disponível e corrige CPF preenchido com zeros <<<
    doc_sacado_fmt = format_doc_pagador(titulo)

    # beneficiário
    agencia = p.get("agencia", "")
    conta = p.get("conta", "")
    digito = p.get("digito", "")
    carteira = p.get("carteira", "")
    beneficiario = p.get("razao_social", "")
    instr1 = p.get("instrucao1", ""); instr2 = p.get("instrucao2", ""); instr3 = p.get("instrucao3", "")
    multa = (p.get("multa", "") or "").strip(); juros = (p.get("juros", "") or "").strip()
    doc_benef_fmt = format_doc(p.get("cnpj", ""))

    # Sacador/Avalista
    sacador_nome = (p.get("sacador_avalista_razao") or "").strip()
    sacador_doc_fmt = format_doc(p.get("sacador_avalista_cnpj") or "")

    codigo_barras = montar_codigo_barras(p, titulo)
    linha_digitavel = montar_linha_digitavel(codigo_barras)
    nn_dv = dv_nosso_numero_base7(carteira, nosso_numero)

    # saída do PDF (mantido como estava)
    pasta_boletos = p.get("pasta_boletos") or "C:/nasapay/boletos"
    os.makedirs(pasta_boletos, exist_ok=True)
    primeiro_nome = sacado.split()[0] if sacado else "Sacado"
    segundo_nome = sacado.split()[1] if len(sacado.split()) > 1 else ""
    nome_pdf = f"Boleto_Nasapay_{primeiro_nome}_{segundo_nome}_{numero_documento}_{vencimento.replace('/', '.')}"
    caminho_pdf = _unique_sequencial(os.path.join(pasta_boletos, nome_pdf + ".pdf"))

    c = canvas.Canvas(caminho_pdf, pagesize=A4)

    # ---- (todo o desenho permanece idêntico) ----
    top_y = altura - 30 * mm
    altura_linha = 6 * mm
    LABEL_PAD = 1.8 * mm
    VALUE_PAD_Y = 4.5 * mm
    CUT_LABEL_GAP = 4.8 * mm
    THIN = 0.4
    THICK = 1.0

    PT_TO_MM = 0.352778
    FONTE_CODIGO_PT = 12
    altura_barras_mm = ((FONTE_CODIGO_PT * PT_TO_MM) + 2.0) * mm
    mid_ajuste_mm = (altura_barras_mm - (FONTE_CODIGO_PT * PT_TO_MM * mm)) / 2 + 1.5 * mm

    instr_spacing = 0.65 * altura_linha
    y_instr1 = top_y - 3 * mm
    y_instr2 = y_instr1 - instr_spacing
    y_instr3 = y_instr2 - instr_spacing

    c.setFont("Times-Roman", 7)
    c.drawCentredString(105 * mm, y_instr1, "Instruções de Impressão")
    c.drawCentredString(105 * mm, y_instr2, "Imprimir em impressora jato de tinta (ink jet) ou laser em qualidade normal. (Não use modo econômico).")
    c.drawCentredString(105 * mm, y_instr3, "Utilize folha A4 (210 x 297 mm) ou Carta (216 x 279 mm) - Corte na linha indicada")

    y_corte1 = y_instr2 - 2 * altura_linha
    c.setDash(1, 2); c.setLineWidth(THICK); c.line(10 * mm, y_corte1, 200 * mm, y_corte1); c.setDash()
    c.setFont("Helvetica-Bold", 8); c.drawRightString(200 * mm, y_corte1 - CUT_LABEL_GAP, "RECIBO DO PAGADOR")

    y1 = y_corte1 - 2.8 * altura_linha - mid_ajuste_mm
    y_base = y1
    if not draw_logo_fit(c, "C:/nasapay/logo_boleto.png", 12 * mm, y_base, 35 * mm, 10 * mm):
        c.setFont("Helvetica-Bold", 10); c.drawString(12 * mm, y_base + 2 * mm, "NASAPAY")
    c.setLineWidth(THIN); c.line(48 * mm, y_base, 48 * mm, y_base + altura_barras_mm)
    c.setLineWidth(THIN); c.line(68 * mm, y_base, 68 * mm, y_base + altura_barras_mm)
    c.setFont("Helvetica-Bold", FONTE_CODIGO_PT); y_text = y_base + mid_ajuste_mm
    c.drawCentredString(58 * mm, y_text, "274-7")
    c.setFont("Helvetica", 6.1); c.drawString(70 * mm, y_text, "BMP SCMEPP LTDA")
    c.setFont("Helvetica-Bold", 10); c.drawRightString(198 * mm, y_text, linha_digitavel)

    col1 = [10, 100, 130, 140, 160, 200]
    for x in col1:
        c.setLineWidth(THIN); c.line(x * mm, y1, x * mm, y1 - altura_linha)
    c.setLineWidth(THIN); c.line(10 * mm, y1, 200 * mm, y1)
    c.setLineWidth(THIN); c.line(10 * mm, y1 - altura_linha, 200 * mm, y1 - altura_linha)
    c.setFont("Times-Roman", 4.5)
    c.drawString(11 * mm, y1 - LABEL_PAD, "Beneficiário Final")
    c.drawString(101 * mm, y1 - LABEL_PAD, "Agência / Código Beneficiário")
    c.drawString(131 * mm, y1 - LABEL_PAD, "Espécie")
    c.drawString(141 * mm, y1 - LABEL_PAD, "Quantidade")
    c.drawString(161 * mm, y1 - LABEL_PAD, "Carteira / Nosso número")
    c.setFont("Helvetica-Bold", 6.1)
    c.drawString(11 * mm,  y1 - VALUE_PAD_Y, pad_left(beneficiario))
    c.drawString(101 * mm, y1 - VALUE_PAD_Y, pad_left(f"{agencia} / {conta}-{digito}"))
    c.drawString(131 * mm, y1 - VALUE_PAD_Y, "R$")
    c.drawRightString(198 * mm, y1 - VALUE_PAD_Y, f"{carteira} / {nosso_numero}-{nn_dv}")

    y2 = y1 - altura_linha
    col2 = [10, 55, 100, 160, 200]
    c.setFillGray(0.93)
    c.rect(100 * mm, y2 - altura_linha, 60 * mm, altura_linha, fill=1, stroke=0)
    c.rect(160 * mm, y2 - altura_linha, 40 * mm, altura_linha, fill=1, stroke=0)
    c.setFillGray(0)
    for x in col2:
        c.setLineWidth(THIN); c.line(x * mm, y2, x * mm, y2 - altura_linha)
    c.setLineWidth(THIN); c.line(10 * mm, y2, 200 * mm, y2)
    c.setLineWidth(THIN); c.line(10 * mm, y2 - altura_linha, 200 * mm, y2 - altura_linha)
    c.setFont("Times-Roman", 4.5)
    c.drawString(11 * mm, y2 - LABEL_PAD, "Número do Documento")
    c.drawString(56 * mm, y2 - LABEL_PAD, "CPF/CNPJ do Beneficiário")
    c.drawString(101 * mm, y2 - LABEL_PAD, "Vencimento")
    c.drawString(161 * mm, y2 - LABEL_PAD, "Valor do Documento")
    c.setFont("Helvetica-Bold", 6.1)
    c.drawString(11 * mm,  y2 - VALUE_PAD_Y, pad_left(numero_documento))
    c.drawString(56 * mm,  y2 - VALUE_PAD_Y, pad_left(doc_benef_fmt))
    c.setFont("Helvetica-Bold", 6.5)
    c.drawString(101 * mm, y2 - VALUE_PAD_Y, pad_left(vencimento))
    c.drawRightString(198 * mm, y2 - VALUE_PAD_Y, f"R$ {valor_fmt}")

    y3 = y2 - altura_linha
    col3 = [10, 40, 80, 120, 160, 200]
    for x in col3:
        c.setLineWidth(THIN); c.line(x * mm, y3, x * mm, y3 - altura_linha)
    c.setLineWidth(THIN); c.line(10 * mm, y3, 200 * mm, y3)
    c.setLineWidth(THIN); c.line(10 * mm, y3 - altura_linha, 200 * mm, y3 - altura_linha)
    c.setFont("Times-Roman", 4.5)
    c.drawString(11 * mm,  y3 - LABEL_PAD, "( - ) Descontos / Abatimentos")
    c.drawString(41 * mm,  y3 - LABEL_PAD, "( - ) Outras Deduções")
    c.drawString(81 * mm,  y3 - LABEL_PAD, "( + ) Mora / Multa")
    c.drawString(121 * mm, y3 - LABEL_PAD, "( + ) Outros Acréscimos")
    c.drawString(161 * mm, y3 - LABEL_PAD, "Valor Cobrado")

    y4 = y3 - altura_linha
    rec_pag_alt = 15 * mm
    c.setLineWidth(THIN); c.line(10 * mm, y4, 200 * mm, y4)
    c.setLineWidth(THIN); c.line(10 * mm, y4 - rec_pag_alt, 200 * mm, y4 - rec_pag_alt)
    c.setLineWidth(THIN); c.line(10 * mm, y4, 10 * mm, y4 - rec_pag_alt)
    c.setLineWidth(THIN); c.line(200 * mm, y4, 200 * mm, y4 - rec_pag_alt)
    c.setFont("Times-Roman", 4.5); c.drawString(11 * mm, y4 - LABEL_PAD, "Pagador")
    c.setFont("Helvetica-Bold", 6.1)
    first_off = 5.0 * mm; gap_off = 3.0 * mm
    c.drawString(11 * mm, y4 - first_off,                 pad_left(f"{sacado} — CPF / CNPJ: {doc_sacado_fmt}"))
    c.drawString(11 * mm, y4 - first_off - gap_off,       pad_left(endereco))
    c.drawString(11 * mm, y4 - first_off - 2*gap_off,     pad_left(f"{(cidade or '')}{' - ' + (uf or '') if uf else ''}{' - ' + (cep or '') if cep else ''}"))

    multa_pct = _parse_pct_to_float(multa)
    juros_pct = _parse_pct_to_float(juros)
    y_free_top = y4 - rec_pag_alt
    y_instr_label_recibo = y_free_top - (1.5 * mm)
    c.setFont("Times-Roman", 4.5)
    c.drawString(11 * mm, y_instr_label_recibo, "Instruções")
    if (multa_pct > 0) or (juros_pct > 0):
        multa_reais = valor_float * (multa_pct / 100.0)
        juros_dia_reais = valor_float * (juros_pct / 100.0)
        multa_txt = format_valor_brl(f"{multa_reais:.2f}")
        juros_txt = format_valor_brl(f"{juros_dia_reais:.2f}")
        msg_rec = f"APÓS VENCIMENTO, COBRAR MULTA DE R$ {multa_txt} + JUROS DE R$ {juros_txt} AO DIA."
        c.setFont("Helvetica-Bold", 6.5)
        c.drawString(11 * mm, y_instr_label_recibo - (3.2 * mm), pad_left(msg_rec.upper()))

    espaco_3linhas = 3 * altura_linha
    y_corte2 = (y4 - rec_pag_alt) - espaco_3linhas
    c.setDash(1, 2); c.setLineWidth(THICK); c.line(10 * mm, y_corte2, 200 * mm, y_corte2); c.setDash()
    c.setFont("Helvetica-Bold", 8); c.drawRightString(200 * mm, y_corte2 - CUT_LABEL_GAP, "FICHA DE COMPENSAÇÃO")
    c.setFont("Helvetica", 9); c.drawRightString(200 * mm, y_corte2 + 1.8 * mm, "✂")

    y_local = y_corte2 - espaco_3linhas

    y_base2 = y_local
    if not draw_logo_fit(c, "C:/nasapay/logo_boleto.png", 12 * mm, y_base2, 35 * mm, 12 * mm):
        c.setFont("Helvetica-Bold", 10); c.drawString(12 * mm, y_base2 + 2 * mm, "NASAPAY")
    c.setLineWidth(THIN); c.line(48 * mm, y_base2, 48 * mm, y_base2 + altura_barras_mm)
    c.setLineWidth(THIN); c.line(68 * mm, y_base2, 68 * mm, y_base2 + altura_barras_mm)
    c.setFont("Helvetica-Bold", FONTE_CODIGO_PT); y_text2 = y_base2 + mid_ajuste_mm
    c.drawCentredString(58 * mm, y_text2, "274-7")
    c.setFont("Helvetica", 6.1)
    c.drawString(70 * mm, y_text2, "BMP SCMEPP LTDA")
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(198 * mm, y_text2, linha_digitavel)

    c.setFillGray(0.93); c.rect(160 * mm, y_local - altura_linha, 40 * mm, altura_linha, fill=1, stroke=0); c.setFillGray(0)
    c.setLineWidth(THICK); c.line(10 * mm, y_local, 200 * mm, y_local)
    c.setLineWidth(THIN);  c.line(10 * mm, y_local - altura_linha, 200 * mm, y_local - altura_linha)
    for x in [10, 160, 200]:
        c.setLineWidth(THIN); c.line(x * mm, y_local, x * mm, y_local - altura_linha)
    c.setFont("Times-Roman", 4.5); c.drawString(11 * mm, y_local - LABEL_PAD, "Local de Pagamento"); c.drawString(161 * mm, y_local - LABEL_PAD, "Vencimento")
    c.setFont("Helvetica-Bold", 6.1); c.drawString(11 * mm, y_local - VALUE_PAD_Y, pad_left("Pagável em qualquer banco até o vencimento"))
    c.setFont("Helvetica-Bold", 6.5); c.drawRightString(198 * mm, y_local - VALUE_PAD_Y, vencimento)

    y_local -= altura_linha
    c.setLineWidth(THIN); c.line(10 * mm, y_local, 200 * mm, y_local)
    c.setLineWidth(THIN); c.line(10 * mm, y_local - altura_linha, 200 * mm, y_local - altura_linha)
    for x in [10, 160, 200]:
        c.setLineWidth(THIN); c.line(x * mm, y_local, x * mm, y_local - altura_linha)
    c.setFont("Times-Roman", 4.5); c.drawString(11 * mm, y_local - LABEL_PAD, "Beneficiário"); c.drawString(161 * mm, y_local - LABEL_PAD, "Agência / Código Beneficiário")
    c.setFont("Helvetica-Bold", 6.1); c.drawString(11 * mm, y_local - VALUE_PAD_Y, pad_left(beneficiario))
    c.drawRightString(198 * mm, y_local - VALUE_PAD_Y, f"{agencia} / {conta}-{digito}")

    y_local -= altura_linha
    for x in [10, 40, 85, 115, 130, 160, 200]:
        c.setLineWidth(THIN); c.line(x * mm, y_local, x * mm, y_local - altura_linha)
    c.setLineWidth(THIN); c.line(10 * mm, y_local, 200 * mm, y_local)
    c.setLineWidth(THIN); c.line(10 * mm, y_local - altura_linha, 200 * mm, y_local - altura_linha)
    c.setFont("Times-Roman", 4.5)
    c.drawString(11 * mm,  y_local - LABEL_PAD, "Data do Documento")
    c.drawString(41 * mm,  y_local - LABEL_PAD, "Nº Documento")
    c.drawString(86 * mm,  y_local - LABEL_PAD, "Espécie Doc.")
    c.drawString(116 * mm, y_local - LABEL_PAD, "Aceite")
    c.drawString(131 * mm, y_local - LABEL_PAD, "Data Processamento")
    c.drawString(161 * mm, y_local - LABEL_PAD, "Carteira / Nosso Número")
    c.setFont("Helvetica-Bold", 6.1)
    c.drawString(11 * mm,  y_local - VALUE_PAD_Y, pad_left(emissao))
    c.drawString(41 * mm,  y_local - VALUE_PAD_Y, pad_left(numero_documento))
    c.drawString(86 * mm,  y_local - VALUE_PAD_Y, "DM")
    c.drawString(116 * mm,  y_local - VALUE_PAD_Y, "N")
    c.drawString(131 * mm, y_local - VALUE_PAD_Y, pad_left(datetime.now().strftime("%d/%m/%Y")))
    c.drawRightString(198 * mm, y_local - VALUE_PAD_Y, f"{carteira} / {nosso_numero}-{nn_dv}")

    y_local -= altura_linha
    c.setFillGray(0.93); c.rect(160 * mm, y_local - altura_linha, 40 * mm, altura_linha, fill=1, stroke=0); c.setFillGray(0)
    for x in [10, 50, 80, 110, 140, 160, 200]:
        c.setLineWidth(THIN); c.line(x * mm, y_local, x * mm, y_local - altura_linha)
    c.setLineWidth(THIN); c.line(10 * mm, y_local, 200 * mm, y_local)
    c.setLineWidth(THIN); c.line(10 * mm, y_local - altura_linha, 200 * mm, y_local - altura_linha)
    c.setFont("Times-Roman", 4.5)
    c.drawString(11 * mm, y_local - LABEL_PAD, "Uso do Banco")
    c.drawString(51 * mm, y_local - LABEL_PAD, "Carteira")
    c.drawString(81 * mm, y_local - LABEL_PAD, "Espécie")
    c.drawString(111 * mm, y_local - LABEL_PAD, "Quantidade")
    c.drawString(141 * mm, y_local - LABEL_PAD, "( x ) Valor")
    c.drawString(161 * mm, y_local - LABEL_PAD, "( = ) Valor Documento")
    c.setFont("Helvetica-Bold", 6.1)
    c.drawString(51 * mm, y_local - VALUE_PAD_Y, pad_left(carteira))
    c.drawString(81 * mm, y_local - VALUE_PAD_Y, "R$")
    c.setFont("Helvetica-Bold", 6.5)
    c.drawRightString(198 * mm, y_local - VALUE_PAD_Y, f"R$ {valor_fmt}")

    y_local -= altura_linha
    bloco_instr_alt = 5 * altura_linha
    c.setLineWidth(THIN); c.line(10 * mm, y_local, 200 * mm, y_local)
    c.setLineWidth(THIN); c.line(10 * mm, y_local - bloco_instr_alt, 200 * mm, y_local - bloco_instr_alt)
    c.setLineWidth(THIN); c.line(10 * mm, y_local, 10 * mm, y_local - bloco_instr_alt)
    c.setLineWidth(THIN); c.line(200 * mm, y_local, 200 * mm, y_local - bloco_instr_alt)
    c.setLineWidth(THIN); c.line(160 * mm, y_local, 160 * mm, y_local - bloco_instr_alt)
    for i in range(1, 5):
        yy = y_local - i * altura_linha
        c.setLineWidth(THIN); c.line(160 * mm, yy, 200 * mm, yy)
    c.setFont("Times-Roman", 4.5)
    c.drawString(11 * mm, y_local - LABEL_PAD, "Instruções (uso do beneficiário)")
    c.drawString(161 * mm, y_local - LABEL_PAD,                  "( - ) Desconto / Abatimentos")
    c.drawString(161 * mm, y_local - LABEL_PAD - 1*altura_linha, "( - ) Outras Deduções")
    c.drawString(161 * mm, y_local - LABEL_PAD - 2*altura_linha, "( + ) Mora / Multa")
    c.drawString(161 * mm, y_local - LABEL_PAD - 3*altura_linha, "( + ) Outros Acréscimos")
    c.drawString(161 * mm, y_local - LABEL_PAD - 4*altura_linha, "( = ) Valor Cobrado")
    y_texto = y_local - VALUE_PAD_Y
    step = 0.55 * altura_linha
    c.setFont("Helvetica", 6.1)
    for linha in [instr1, instr2, instr3]:
        if linha:
            c.drawString(11 * mm, y_texto, pad_left(linha))
            y_texto -= step

    if (multa_pct > 0) or (juros_pct > 0):
        multa_reais = valor_float * (multa_pct / 100.0)
        juros_dia_reais = valor_float * (juros_pct / 100.0)
        multa_txt = format_valor_brl(f"{multa_reais:.2f}")
        juros_txt = format_valor_brl(f"{juros_dia_reais:.2f}")
        msg = f"APÓS VENCIMENTO, COBRAR MULTA DE R$ {multa_txt} + JUROS DE R$ {juros_txt} AO DIA."
        c.setFont("Helvetica-Bold", 6.5)
        c.drawString(11 * mm, y_texto, pad_left(msg.upper()))

    y_local = y_local - bloco_instr_alt
    pag_alt = 12 * mm
    c.setLineWidth(THIN); c.line(10 * mm, y_local, 200 * mm, y_local)
    c.setLineWidth(THIN); c.line(10 * mm, y_local - pag_alt, 200 * mm, y_local - pag_alt)
    c.setLineWidth(THIN); c.line(10 * mm, y_local, 10 * mm, y_local - pag_alt)
    c.setLineWidth(THIN); c.line(200 * mm, y_local, 200 * mm, y_local - pag_alt)
    c.setFont("Times-Roman", 4.5); c.drawString(11 * mm, y_local - LABEL_PAD, "Pagador")
    c.setFont("Helvetica-Bold", 6.1)
    first_off = 4.2 * mm; gap_off = 2.6 * mm
    c.drawString(11 * mm, y_local - first_off,                 pad_left(f"{sacado} — CPF / CNPJ: {doc_sacado_fmt}"))
    c.drawString(11 * mm, y_local - first_off - gap_off,       pad_left(endereco))
    c.drawString(11 * mm, y_local - first_off - 2*gap_off,     pad_left(f"{(cidade or '')}{' - ' + (uf or '') if uf else ''}{' - ' + (cep or '') if cep else ''}"))

    y_local -= pag_alt
    c.setFont("Times-Roman", 6)
    FOOTER_OFFSET = 2.6 * mm

    c.drawString(10 * mm,  y_local - FOOTER_OFFSET, "Sacador/Avalista:")
    if sacador_nome or sacador_doc_fmt:
        c.setFont("Helvetica-Bold", 6.1)
        linha_sa = sacador_nome
        if sacador_doc_fmt:
            linha_sa = (linha_sa + f" — CNPJ: {sacador_doc_fmt}") if linha_sa else f"CNPJ: {sacador_doc_fmt}"
        c.drawString(26 * mm, y_local - FOOTER_OFFSET, linha_sa)

    c.setFont("Times-Roman", 6)
    c.drawRightString(200 * mm, y_local - FOOTER_OFFSET, "Autenticação Mecânica — Ficha de Compensação")

    x_bar = 10 * mm
    y_bar = max(18 * mm, y_local - 18 * mm)
    if I25 is not None:
        barras = I25(codigo_barras, barHeight=13 * mm, barWidth=0.33 * mm, quiet=True)
        barras.drawOn(c, x_bar, y_bar)
    else:
        draw_i25(c, codigo_barras, x_bar, y_bar, barWidth=0.33 * mm, barHeight=13 * mm)

    c.showPage()
    c.save()

    try:
        store.init_db()
        boleto_id = store.record_boleto(titulo, caminho_pdf, p)
        print(f"[store] boleto registrado id={boleto_id} file={caminho_pdf}", flush=True)
    except Exception as e:
        print(f"[store] aviso: não consegui registrar o boleto no banco: {e}", flush=True)

    return caminho_pdf

# --------------- fluxo de uso ---------------

def _dialogo_falta_nn():
    top = tk.Toplevel()
    top.title("Nosso Número ausente")
    ttk.Label(top, text="Título(s) selecionado(s) ainda não possui(em) Nosso Número Nasapay.", font=("Segoe UI", 10, "bold")).pack(padx=14, pady=(14,6))
    ttk.Label(top, text="Você deseja gerar o Nosso Número agora?").pack(padx=14)
    btns = ttk.Frame(top); btns.pack(pady=12)
    escolha = {"ok": False, "origem": None}

    def cancelar():
        escolha["ok"] = False; top.destroy()

    def gerar():
        sub = tk.Toplevel(top); sub.title("Escolha a origem")
        ttk.Label(sub, text="Selecione a origem para gerar o Nosso Número:").pack(padx=12, pady=(12,8))
        def _set(v): escolha["ok"]=True; escolha["origem"]=v; sub.destroy(); top.destroy()
        ttk.Button(sub, text="XML", command=lambda: _set("xml")).pack(padx=8, pady=4, fill="x")
        ttk.Button(sub, text="CNAB 400 Bradesco", command=lambda: _set("cnab")).pack(padx=8, pady=4, fill="x")
        sub.grab_set(); sub.lift()

    ttk.Button(btns, text="Cancelar", command=cancelar).pack(side="left", padx=6)
    ttk.Button(btns, text="Gerar Nosso Número", command=gerar).pack(side="right", padx=6)

    try:
        top.grab_set(); top.lift(); top.focus_force()
        top.attributes("-topmost", True); top.after(200, lambda: top.attributes("-topmost", False))
    except Exception: pass

    top.wait_window()
    return escolha["ok"], escolha["origem"]

def imprimir_boletos():
    p = carregar_parametros()
    caminho_entrada = (
        p.get("pasta_importar_remessa")
        or p.get("pasta_entrada")
        or os.path.expanduser("~")
    )

    arquivos = filedialog.askopenfilenames(
        initialdir=caminho_entrada,
        filetypes=[("Arquivos CNAB/XML", "*.xml *.REM *.TXT")]
    )
    if not arquivos:
        return

    try:
        store.init_db()
    except Exception as e:
        print(f"[store] init_db falhou: {e}", flush=True)

    gerados_total: list[str] = []

    for arquivo in arquivos:
        try:
            titulos = extrair_titulos_de_arquivo(arquivo, carregar_parametros())
            if not titulos:
                messagebox.showinfo("Aviso", f"Nenhum título extraído de {arquivo}.")
                continue

            falta_nn = any(not (t.get("nosso_numero") and str(t.get("nosso_numero")).strip()) for t in titulos)
            if falta_nn:
                ok, origem = _dialogo_falta_nn()
                if not ok:
                    continue
                try:
                    if origem == "xml":
                        from src.conversor_xml import converter_arquivo_xml
                        converter_arquivo_xml()
                    else:
                        from src.conversor_bradesco import converter_arquivo_bradesco
                        converter_arquivo_bradesco()
                    messagebox.showinfo("Conversão concluída",
                                        "Nosso Número gerado pela conversão.\nAgora volte e gere o boleto novamente.")
                except Exception as e:
                    messagebox.showerror("Erro", f"Falha ao converter: {e}")
                    continue

            for t in titulos:
                try:
                    pdf_path = gerar_boleto_titulos(t)
                    gerados_total.append(pdf_path)
                except Exception as e:
                    messagebox.showerror("Erro", f"Erro ao processar {arquivo}:\n{e}")
                    continue

        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao processar {arquivo}:\n{e}")

    if gerados_total:
        _popup_boletos_gerados(gerados_total)
