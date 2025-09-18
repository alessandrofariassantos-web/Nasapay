# === src/extrator_titulos.py ===
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from utils.nn_registry import buscar_nosso_numero

# ---------------- helpers ----------------

_DIGITS = re.compile(r"\D")

def _digits(s: str) -> str:
    return _DIGITS.sub("", str(s or ""))

def _doc_base_sem_dv(s: str) -> str:
    """
    Remove DV no final do documento.
    Exemplos que viram 'BASE':
      '0000003672-3' → '0000003672'
      '0000003672/3' → '0000003672'
      '0000003672.3' → '0000003672'
      '0000003672'   → '0000003672'
    """
    s = (s or "").strip()
    m = re.match(r"^\s*(\d{1,30})\s*[-/\.]\s*\d\s*$", s)
    if m:
        return m.group(1)
    return _digits(s)

def _doc_pagador_14(s: str) -> str:
    """Retorna CPF/CNPJ com 14 dígitos (CPF recebe zeros à esquerda)."""
    d = _digits(s)
    if len(d) > 14:
        d = d[-14:]
    return d.rjust(14, "0")

def _formatar_cep(c):
    d = _digits(c)
    return f"{d[:5]}-{d[5:]}" if len(d) == 8 else c or ""

def _formatar_fone(f):
    d = _digits(f)
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return f or ""

# ---------------- API principal ----------------

def extrair_titulos_de_arquivo(arquivo, parametros):
    """
    Retorna lista de títulos em um formato único para a app.
    Cada título é um dict com chaves como: sacado, documento, valor, vencimento, emissao, sacado_endereco, sacado_cnpj etc.
    Se houver Nosso Número previamente registrado, ele já é atribuído (campo 'nosso_numero').
    """
    try:
        low = (arquivo or "").lower()
        if low.endswith(".xml"):
            return extrair_de_xml(arquivo, parametros)
        elif low.endswith((".rem", ".txt")):
            return extrair_de_bradesco(arquivo, parametros)
        else:
            raise RuntimeError("Formato de arquivo não suportado. Use XML ou CNAB400 (.REM/.TXT).")
    except Exception as e:
        raise Exception(f"Erro ao extrair dados de {os.path.basename(arquivo)}: {e}")

# ---------------- XML NFe ----------------

def extrair_de_xml(arquivo, parametros):
    ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}
    tree = ET.parse(arquivo)
    root = tree.getroot()

    ide = root.find(".//nfe:ide", namespaces=ns)
    dest = root.find(".//nfe:dest", namespaces=ns)

    nfe_num = (ide.findtext("nfe:nNF", default="", namespaces=ns) or "").strip()

    emissao = ""
    emissao_raw = (ide.findtext("nfe:dhEmi", default="", namespaces=ns) or "")[:10]
    if emissao_raw:
        try:
            emissao = datetime.strptime(emissao_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            emissao = emissao_raw

    # Sacado
    sacado_nome = (dest.findtext("nfe:xNome", default="", namespaces=ns) or "").strip()
    sacado_cnpj = (dest.findtext("nfe:CNPJ", default="", namespaces=ns)
                   or dest.findtext("nfe:CPF", default="", namespaces=ns) or "").strip()

    end = dest.find(".//nfe:enderDest", namespaces=ns)
    xLgr = (end.findtext("nfe:xLgr", "", namespaces=ns) or "").strip()
    nro = (end.findtext("nfe:nro", "", namespaces=ns) or "").strip()
    xBairro = (end.findtext("nfe:xBairro", "", namespaces=ns) or "").strip()
    cidade = (end.findtext("nfe:xMun", "", namespaces=ns) or "").strip()
    uf = (end.findtext("nfe:UF", "", namespaces=ns) or "").strip()
    cep = (end.findtext("nfe:CEP", "", namespaces=ns) or "").strip()
    fone = (end.findtext("nfe:fone", "", namespaces=ns)
            or dest.findtext("nfe:fone", "", namespaces=ns) or "").strip()
    endereco_str = f"{xLgr}, {nro} - {xBairro}".strip().strip(", -")

    cep_fmt = _formatar_cep(cep)
    fone_fmt = _formatar_fone(fone)

    titulos = []
    for dup in root.findall(".//nfe:dup", namespaces=ns):
        parcela = (dup.findtext("nfe:nDup", default="", namespaces=ns) or "").strip()

        vencimento = ""
        venc_raw = (dup.findtext("nfe:dVenc", default="", namespaces=ns) or "").strip()
        if venc_raw:
            try:
                vencimento = datetime.strptime(venc_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
            except Exception:
                vencimento = venc_raw

        valor = (dup.findtext("nfe:vDup", default="0,00", namespaces=ns) or "0,00").strip()

        doc_composto = f"{nfe_num}-{parcela}" if parcela else nfe_num
        t = {
            "sacado": sacado_nome,
            "documento": _doc_base_sem_dv(doc_composto),
            "valor": valor,
            "vencimento": vencimento,
            "emissao": emissao,
            "sacado_cnpj": _doc_pagador_14(sacado_cnpj),
            "sacado_endereco": endereco_str,
            "sacado_cidade": cidade,
            "sacado_uf": uf,
            "sacado_cep": cep_fmt,
            "sacado_fone": fone_fmt,
        }
        nn = buscar_nosso_numero(t)
        if nn:
            t["nosso_numero"] = nn
        titulos.append(t)

    return titulos

# ---------------- CNAB400 Bradesco (.REM/.TXT) ----------------

def extrair_de_bradesco(arquivo, parametros):
    """
    Extrai títulos do CNAB400 Bradesco (registro detalhe = linhas com '1').
    Campos que usamos:
      - documento (111–120)
      - vencimento (121–126)
      - valor (127–139) em centavos
      - emissão (150–156)
      - pagador doc (221–234)
      - nome (235–274)
      - endereço (275–314)
    """
    titulos = []
    with open(arquivo, "r", encoding="latin-1") as f:
        for ln in f:
            if not ln or ln[0] != "1":
                continue
            l = ln.rstrip("\r\n")
            try:
                documento = l[110:120].strip()
                vencimento = datetime.strptime(l[120:126], "%d%m%y").strftime("%d/%m/%Y")
                valor_cent = int(l[126:139])
                valor = f"{valor_cent/100:.2f}".replace(".", ",")
                emissao = datetime.strptime(l[150:156], "%d%m%y").strftime("%d/%m/%Y")
                cnpj_cpf = l[220:234].strip()
                nome_sacado = l[234:274].strip()
                endereco = l[274:314].strip()
            except Exception as e:
                # pula linha mal formatada, mas loga no console
                print(f"[extrair_de_bradesco] linha ignorada: {e}")
                continue

            t = {
                "sacado": nome_sacado,
                "documento": _doc_base_sem_dv(documento),   # normaliza para bater com a chave do registro
                "valor": valor,
                "vencimento": vencimento,
                "emissao": emissao,
                "sacado_cnpj": _doc_pagador_14(cnpj_cpf),   # 14 dígitos
                "sacado_endereco": endereco,
                "sacado_cidade": "",
                "sacado_uf": "",
                "sacado_cep": "",
                "sacado_fone": "",
            }
            nn = buscar_nosso_numero(t)
            if nn:
                t["nosso_numero"] = nn
            titulos.append(t)

    return titulos
