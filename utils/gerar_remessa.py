# utils/gerar_remessa.py
import os, re, zipfile, unicodedata
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox

from utils.popup_confirmacao import popup_confirmacao_titulos
from utils.parametros import carregar_parametros, salvar_parametros
from utils.nn_registry import registrar_titulos
from utils.boletos_bmp import dv_nosso_numero_base7  # DV do Nosso Número

# ======================== helpers básicos ========================

def _set_range(buf: list, start_1b: int, end_1b: int, value: str, *, zfill=False):
    """Escreve 'value' nas posições [start..end] (1-based, inclusive)."""
    width = end_1b - start_1b + 1
    v = (value or "")
    if zfill:
        v = re.sub(r"\s+", "", v)[:width].rjust(width, "0")
    else:
        v = v.ljust(width)[:width]
    buf[start_1b - 1:end_1b] = list(v)

def _dig(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def _alfan(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return re.sub(r"[^A-Za-z0-9 \-\.\/\&]", " ", s)

def _linha_vazia(t: str) -> list:
    """Cria um buffer de 400 chars com tipo t na posição 1."""
    ln = [" "] * 400
    _set_range(ln, 1, 1, t)
    return ln

def _set_seq_final(buf: list, n: int):
    """Numeração do registro nas pos. 395–400 (6 dígitos)."""
    _set_range(buf, 395, 400, str(n).zfill(6))

def _centavos_from_brl(valor_str: str) -> int:
    """Converte '1.234,56' / '1234,56' / '1234.56' / 1234.56 -> centavos (int)."""
    if valor_str is None:
        return 0
    s = str(valor_str).strip().replace(" ", "")
    if s == "":
        return 0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except Exception:
        v = float(int(_dig(s) or 0))
    return int(round(max(0.0, v) * 100))

def _fmt_date_ddmmaa(date_str: str) -> str:
    """Entrada: 'DD/MM/AAAA' ou 'AAAA-MM-DD' -> 'DDMMAA'."""
    if not date_str:
        return "000000"
    s = date_str.strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.strftime("%d%m%y")
        except Exception:
            pass
    d = _dig(s)
    if len(d) == 8:  # DDMMAAAA
        return d[:4] + d[-2:]
    return "000000"

def _pct_to_hundredths3(pct_str: str) -> str:
    """
    Converte percentual str para 3 dígitos em CENTÉSIMOS de %.
    Ex.: '2,00' -> 200; '9,99' -> 999; '0' -> 000.
    """
    s = (pct_str or "").strip()
    if s == "":
        return "000"
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except Exception:
        v = 0.0
    n = int(round(v * 100))
    n = max(0, min(999, n))
    return f"{n:03d}"

def _juros_dia_centavos(valor_brl: str, juros_pct_str: str) -> int:
    """
    Juros ao dia em centavos = (valor_em_centavos) * (percentual/100).
    Ex.: R$ 1.000,00 e '0,10' -> 100 centavos/dia.
    """
    base = _centavos_from_brl(valor_brl)
    s = (juros_pct_str or "").strip()
    if s == "":
        return 0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        pct = float(s)
    except Exception:
        pct = 0.0
    return int(round(base * (pct / 100.0)))

# ======================== sequencial contínuo ========================

def _proximo_sequencial(cfg: dict) -> int:
    """Lê cfg['ultima_remessa'] (7 dígitos), soma 1 e retorna int."""
    try:
        atual = int(_dig(cfg.get("ultima_remessa", "0")) or "0")
    except Exception:
        atual = 0
    return max(0, atual) + 1

def _persistir_sequencial(cfg: dict, seq: int):
    """Salva o novo sequencial (7 dígitos) em cfg['ultima_remessa'] e persiste o config."""
    cfg["ultima_remessa"] = str(seq).zfill(7)
    salvar_parametros(cfg)

def _codigo_arquivo_remessa(seq: int, data: datetime) -> str:
    """CB + DDMM + SEQ(7) — ex.: CB12080000001"""
    ddmm = data.strftime("%d%m")
    return f"CB{ddmm}{seq:07d}"

# ======================== HEADER BMP ========================

def montar_header_bmp(param: dict, seq_remessa: int, data_geracao: datetime, nro_registro: int=1) -> str:
    ag4   = _dig(param.get("agencia", ""))[:4].rjust(4, "0")
    ced7  = _dig(param.get("codigo_cedente", ""))[:7].rjust(7, "0")
    crt2  = _dig(param.get("carteira", ""))[:2].rjust(2, "0")
    rz30  = _alfan(param.get("razao_social", "")).upper()[:30]
    hoje  = data_geracao.strftime("%d%m%y")

    ln = _linha_vazia("0")
    _set_range(ln, 2, 2, "1")  # <<< posição 2 = '1'
    _set_range(ln, 3,  9,  "REMESSA")
    _set_range(ln,10, 11,  "01")
    _set_range(ln,12, 26,  "COBRANCA")
    _set_range(ln,27, 33,  "0000000")
    _set_range(ln,34, 37,  ag4)
    _set_range(ln,38, 44,  ced7)
    _set_range(ln,45, 46,  crt2)
    _set_range(ln,47, 76,  rz30)
    _set_range(ln,77, 79,  "274")
    _set_range(ln,80, 94,  "BMP MONEY PLUS")
    _set_range(ln,95,100,  hoje)
    _set_range(ln,109,110, "MX")
    _set_range(ln,111,117, str(seq_remessa).zfill(7))
    _set_seq_final(ln, nro_registro)
    header = "".join(ln)
    assert len(header) == 400, f"HEADER len={len(header)}"
    return header

# ======================== DETALHE TIPO 1 ========================

def montar_detalhe_bmp(titulo: dict, param: dict, nro_registro: int) -> str:
    """
    TIPO 1 conforme instruções do cliente (posições 1-based, inclusivas).
    """
    ln = _linha_vazia("1")

    # Cadastro
    ag4     = _dig(param.get("agencia", ""))[:4].rjust(4, "0")    # 26–29
    conta7  = _dig(param.get("conta", ""))[:7].rjust(7, "0")      # 30–36
    dig_cc  = _dig(param.get("digito", ""))[:1] or "0"            # 37
    carteira= _dig(param.get("carteira", ""))[:2].rjust(2, "0")   # 23–24

    # Título
    doc      = (titulo.get("documento") or "")
    doc_10   = _dig(doc)[-10:].rjust(10, "0")                     # 111–120 (numérico, zeros à esquerda)
    venc_ddmmaa  = _fmt_date_ddmmaa(titulo.get("vencimento") or "")
    emiss_ddmmaa = _fmt_date_ddmmaa(titulo.get("emissao") or "")
    valor_cent = _centavos_from_brl(titulo.get("valor") or "0")
    valor_13  = f"{valor_cent:013d}"                              # 127–139

    # Nosso número + DV
    nn11  = _dig(titulo.get("nosso_numero", ""))[:11].rjust(11, "0")
    dv_nn = dv_nosso_numero_base7(carteira, nn11)

    # Multa e juros
    multa_068_070 = _pct_to_hundredths3(param.get("multa", "0"))  # 68–70 (centésimos)
    juros_dia_cent = _juros_dia_centavos(titulo.get("valor") or "0", param.get("juros", "0"))
    juros_161_173  = f"{juros_dia_cent:013d}"

    # Pagador
    raw_doc_pag = _dig(titulo.get("sacado_cnpj") or titulo.get("doc_pagador") or "")
    tipo_insc = "02" if len(raw_doc_pag) == 14 else ("01" if len(raw_doc_pag) == 11 else "02")
    doc_pag = (raw_doc_pag[-14:]).rjust(14, "0")  # à direita; CPF completa zeros à esquerda

    sacado_nome = (titulo.get("sacado") or "")
    end_comp    = (titulo.get("sacado_endereco") or "")
    cep         = _dig(titulo.get("sacado_cep") or "")
    cep8        = (cep[-8:]).rjust(8, "0") if cep else "00000000"

    # ===== Preenchimentos =====

    # 2–6 zeros
    _set_range(ln, 2, 6, "00000")
    # 7 branco
    _set_range(ln, 7, 7, "")
    # 8–12 zeros
    _set_range(ln, 8, 12, "00000")
    # 13–19 zeros
    _set_range(ln, 13, 19, "0000000")
    # 20 branco
    _set_range(ln, 20, 20, "")
    # 21–22 zeros
    _set_range(ln, 21, 22, "00")

    # 23–24 carteira (2)
    _set_range(ln, 23, 24, carteira, zfill=True)

    # 25–29 agência: 25 = '0' e 26–29 = agência (4 dígitos)
    _set_range(ln, 25, 25, "0")
    _set_range(ln, 26, 29, ag4, zfill=True)

    # 30–36 conta (7)
    _set_range(ln, 30, 36, conta7, zfill=True)
    # 37 dígito conta
    _set_range(ln, 37, 37, dig_cc, zfill=True)

    # 38–62 zeros
    _set_range(ln, 38, 62, "0" * 25)

    # 63–65 zeros
    _set_range(ln, 63, 65, "000")

    # 66–67 '20'
    _set_range(ln, 66, 67, "20")

    # 68–70 multa (centésimos conforme cadastro)
    _set_range(ln, 68, 70, multa_068_070, zfill=True)

    # 71–81 nosso número (11)
    _set_range(ln, 71, 81, nn11, zfill=True)
    # 82 DV do NN
    _set_range(ln, 82, 82, dv_nn)

    # 83–92 zeros
    _set_range(ln, 83, 92, "0" * 10)

    # 93 '2' | 94 'N'
    _set_range(ln, 93, 93, "2")
    _set_range(ln, 94, 94, "N")

    # 95–105 brancos
    _set_range(ln, 95, 105, "")
    # 106 '0'
    _set_range(ln, 106, 106, "0")
    # 107–108 brancos
    _set_range(ln, 107, 108, "")
    # 109–110 '01'
    _set_range(ln, 109, 110, "01")

    # 111–120 nº documento (10, zeros à esquerda)
    _set_range(ln, 111, 120, doc_10, zfill=True)

    # 121–126 vencimento (DDMMAA)
    _set_range(ln, 121, 126, venc_ddmmaa)
    # 127–139 valor (13)
    _set_range(ln, 127, 139, valor_13, zfill=True)

    # 140–147 zeros
    _set_range(ln, 140, 147, "0" * 8)

    # 148–149 espécie (2)
    esp = _dig(param.get("especie", ""))[:2].rjust(2, "0")
    _set_range(ln, 148, 149, esp)

    # 150 'N'
    _set_range(ln, 150, 150, "N")

    # 151–156 emissão (DDMMAA)
    _set_range(ln, 151, 156, emiss_ddmmaa)

    # 157–160 zeros
    _set_range(ln, 157, 160, "0000")

    # 161–173 juros ao dia (centavos, 13 dígitos)
    _set_range(ln, 161, 173, juros_161_173, zfill=True)

    # 174–179 brancos
    _set_range(ln, 174, 179, "")

    # 180–218 zeros
    _set_range(ln, 180, 218, "0" * 39)

    # 219–220 tipo inscrição (01 CPF / 02 CNPJ)
    _set_range(ln, 219, 220, tipo_insc)
    # 221–234 nº inscrição pagador (direita; zeros à esquerda)
    _set_range(ln, 221, 234, doc_pag)

    # 235–274 nome pagador (40)
    _set_range(ln, 235, 274, _alfan(sacado_nome).upper()[:40])

    # 275–314 endereço completo (40)
    _set_range(ln, 275, 314, _alfan(end_comp).upper()[:40])

    # 315–326 branco
    _set_range(ln, 315, 326, "")

    # 327–334 CEP (8 dígitos)
    _set_range(ln, 327, 334, cep8)

    # 335–350 zeros
    _set_range(ln, 335, 350, "0" * 16)

    # 351–394 branco
    _set_range(ln, 351, 394, "")

    # 395–400 sequencial
    _set_seq_final(ln, nro_registro)

    det = "".join(ln)
    assert len(det) == 400, f"DETALHE len={len(det)}"
    return det

def montar_trailer_bmp(qtde_registros: int) -> str:
    ln = _linha_vazia("9")
    _set_seq_final(ln, qtde_registros)
    return "".join(ln)

# ======================== Pop-up “Remessa Gerada” (novo estilo) ========================

def _popup_remessa_gerada(arquivos_rem: list[str], parent=None, pasta_saida: str = ""):
    top = tk.Toplevel(parent) if parent else tk.Toplevel()
    top.title("Remessa Gerada")
    try:
        if parent is not None:
            top.transient(parent)
        top.grab_set(); top.lift(); top.focus_force()
        top.attributes("-topmost", True); top.after(200, lambda: top.attributes("-topmost", False))
    except Exception:
        pass

    total = sum(1 for _ in arquivos_rem)  # um por chamada (mas já preparado para vários)
    pasta = pasta_saida or (os.path.dirname(arquivos_rem[0]) if arquivos_rem else "")

    frame = ttk.Frame(top); frame.pack(fill="both", expand=True, padx=16, pady=12)

    ttk.Label(frame, text=f"Quantidade de Títulos Gerados: {total:03d}", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(0,6))

    if total <= 1:
        ttk.Label(frame, text="Nome do Arquivo Remessa Gerado:", font=("Segoe UI", 10)).pack(anchor="w")
    else:
        ttk.Label(frame, text="Nomes dos Arquivos Remessa Gerados:", font=("Segoe UI", 10)).pack(anchor="w")

    nomes = [os.path.basename(p) for p in arquivos_rem]

    # Área rolável (se necessário)
    canvas = tk.Canvas(frame, width=640, height=min(280, 22*max(3, len(nomes))), highlightthickness=0)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
    inner = ttk.Frame(canvas)
    inner_id = canvas.create_window((0,0), window=inner, anchor="nw")
    canvas.configure(yscrollcommand=scroll.set)

    def _on_cfg(_=None):
        canvas.configure(scrollregion=canvas.bbox("all"))
    inner.bind("<Configure>", _on_cfg)

    for nm in nomes:
        ttk.Label(inner, text="• "+nm).pack(anchor="w")

    canvas.pack(side="left", fill="both", expand=True, pady=(2,2))
    scroll.pack(side="left", fill="y")

    ttk.Label(frame, text=f"Local: {pasta}", foreground="#444").pack(anchor="w", pady=(8,0))

    btns = ttk.Frame(frame); btns.pack(anchor="e", pady=(12,0))
    def abrir_local():
        try: os.startfile(pasta)
        except Exception as e: messagebox.showerror("Erro", f"Não consegui abrir a pasta:\n{e}", parent=top)
    ttk.Button(btns, text="Abrir Local do Arquivo", command=abrir_local).pack(side="left", padx=6)
    ttk.Button(btns, text="OK", command=top.destroy).pack(side="left", padx=6)

# ======================== Geração da remessa ========================

def gerar_remessa_e_zip(titulos: list[dict], parametros: dict, parent=None):
    """
    1) Gera remessa (HEADER + DETALHES + TRAILER)
    2) Persiste sequencial e registra NNs no CSV
    3) Popup “Remessa Gerada” (novo estilo)
    4) Confirmação de Títulos (com TOTAL e QTD Total)
    """
    if not titulos:
        messagebox.showinfo("Aviso", "Nenhum título para remessa.", parent=parent)
        return

    cfg  = carregar_parametros()
    hoje = datetime.now()

    seq = _proximo_sequencial(cfg)
    codigo_cb = _codigo_arquivo_remessa(seq, hoje)

    pasta_saida = parametros.get("pasta_saida") or r"C:/nasapay/remessas"
    os.makedirs(pasta_saida, exist_ok=True)
    nome_base   = f"{codigo_cb}"
    path_rem    = os.path.join(pasta_saida, f"{nome_base}.REM")

    # Montagem
    linhas = []
    linhas.append(montar_header_bmp(parametros, seq_remessa=seq, data_geracao=hoje, nro_registro=1))

    nro = 2
    for t in titulos:
        linhas.append(montar_detalhe_bmp(t, parametros, nro_registro=nro))
        nro += 1

    linhas.append(montar_trailer_bmp(qtde_registros=nro))

    with open(path_rem, "w", encoding="latin-1", newline="") as f:
        for ln in linhas:
            f.write(ln + "\r\n")

    try:
        from utils.validador_remessa import validar_arquivo_remessa as _val
        _val(path_rem)
    except Exception:
        pass

    _persistir_sequencial(cfg, seq)
    try:
        registrar_titulos(titulos, parametros, meta={"arquivo": path_rem})
    except Exception as e:
        print(f"[nn_registry] aviso: não consegui registrar os títulos: {e}")

    try:
        path_zip = os.path.join(pasta_saida, f"{nome_base}.zip")
        with zipfile.ZipFile(path_zip, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(path_rem, arcname=os.path.basename(path_rem))
    except Exception:
        pass

    # Popup novo
    try:
        _popup_remessa_gerada([path_rem], parent=parent, pasta_saida=pasta_saida)
    except Exception as e:
        print("[ui] falha ao exibir popup da remessa:", e)

    try:
        popup_confirmacao_titulos(titulos, parent=parent)
    except Exception:
        pass

    return path_rem
