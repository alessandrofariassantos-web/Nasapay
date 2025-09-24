# src/conversor_bb240.py
import os
from datetime import datetime
from tkinter import filedialog, messagebox

from utils.parametros import carregar_parametros, gerar_nosso_numero
from utils.gerar_remessa import gerar_remessa_e_zip

def _dig(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _fmt_ddmmaaaa_to_ddmmyyyy(s: str) -> str:
    s = (s or "").strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[0:2]}/{s[2:4]}/{s[4:8]}"
    return s

SEG_IDX_TIPO_REG = 7   # registro detalhe '3'
SEG_IDX_COD_SEG  = 13  # 'P' / 'Q'

def _parse_cnab240_bb(caminho: str, parametros: dict) -> list[dict]:
    titulos = []
    segP, segQ = {}, {}

    with open(caminho, "r", encoding="latin-1") as f:
        for ln in f:
            if not ln or len(ln) < 240:
                continue
            try:
                if ln[SEG_IDX_TIPO_REG] != '3':
                    continue
                seg = ln[SEG_IDX_COD_SEG]

                try:
                    seq_reg = int(ln[8:13])  # 9–13 (1-based)
                except Exception:
                    seq_reg = None

                if seg == 'P':
                    seu_numero = ln[62:77].strip()   # 63–77
                    venc_raw   = ln[77:85]           # 78–85 DDMMAAAA
                    valor_raw  = ln[85:100]          # 86–100 13+2
                    emiss_raw  = ln[110:118]         # 111–118

                    vencimento = _fmt_ddmmaaaa_to_ddmmyyyy(venc_raw)
                    emissao    = _fmt_ddmmaaaa_to_ddmmyyyy(emiss_raw)
                    try:
                        valor_cent = int(valor_raw)
                        valor = f"{valor_cent/100:.2f}".replace('.', ',')
                    except Exception:
                        valor = "0,00"

                    segP[seq_reg] = {
                        "documento": seu_numero,
                        "vencimento": vencimento,
                        "valor": valor,
                        "emissao": emissao,
                    }

                elif seg == 'Q':
                    tipo_insc = ln[18:20]            # 19–20
                    doc       = _dig(ln[20:35])      # 21–35
                    nome      = ln[35:75].strip()    # 36–75
                    end       = ln[75:115].strip()   # 76–115
                    bairro    = ln[115:130].strip()  # 116–130
                    cep       = _dig(ln[130:138])    # 131–138
                    cidade    = ln[138:153].strip()  # 139–153
                    uf        = ln[153:155].strip()  # 154–155

                    if tipo_insc.strip() == '01':
                        doc_fmt = doc[-11:].rjust(11, '0')
                    else:
                        doc_fmt = doc[-14:].rjust(14, '0')

                    segQ[seq_reg] = {
                        "doc_pagador_tipo": '01' if tipo_insc.strip() == '01' else '02',
                        "sacado_cnpj": doc_fmt,
                        "sacado": nome,
                        "sacado_endereco": f"{end} - {bairro}".strip(" -"),
                        "sacado_cidade": cidade,
                        "sacado_uf": uf,
                        "sacado_cep": cep,
                    }
            except Exception:
                continue

    chaves = sorted(set(k for k in segP.keys() if k in segQ))
    import re
    for k in chaves:
        base = {}
        base.update(segP.get(k, {}))
        base.update(segQ.get(k, {}))

        if not base.get("documento"):
            continue

        # Normaliza documento removendo DV tipo 12345-1 / 12345/1 / 12345.1
        doc = base.get("documento", "").strip()
        m = re.match(r"^\\s*(\\d{1,30})\\s*[-\\/.]\\s*\\d\\s*$", doc)
        if m:
            base["documento"] = m.group(1)

        base["nosso_numero"] = gerar_nosso_numero(parametros)
        titulos.append(base)

    return titulos

def converter_arquivo_bb240():
    p = carregar_parametros() or {}
    caminho_entrada = (
        p.get("pasta_importar_remessa")
        or p.get("pasta_entrada")
        or os.path.expanduser("~")
    )

    arquivo = filedialog.askopenfilename(
        initialdir=caminho_entrada,
        filetypes=[("Arquivos CNAB240", "*.REM *.TXT *.240")]
    )
    if not arquivo:
        return

    try:
        titulos = _parse_cnab240_bb(arquivo, p)
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao ler CNAB240: {e}")
        return

    if not titulos:
        messagebox.showinfo("Aviso", "Nenhum título encontrado no arquivo selecionado.")
        return

    gerar_remessa_e_zip(titulos, p)