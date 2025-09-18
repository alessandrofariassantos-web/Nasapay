# src/conversor_bradesco.py
from datetime import datetime
from tkinter import filedialog, messagebox

from utils.parametros import carregar_parametros, gerar_nosso_numero
from utils.gerar_remessa import gerar_remessa_e_zip

def _digits(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isdigit())

def _normalize_tipo_insc(raw: str) -> str:
    s = "".join(ch for ch in (raw or "") if ch.isdigit())
    if s in ("1", "01"):
        return "01"
    if s in ("2", "02"):
        return "02"
    return "02"

def converter_arquivo_bradesco():
    parametros = carregar_parametros() or {}

    caminho_entrada = (
        parametros.get("pasta_importar_remessa")
        or parametros.get("pasta_entrada")
        or ""
    )

    arquivo = filedialog.askopenfilename(
        initialdir=caminho_entrada,
        filetypes=[("Arquivos CNAB400", "*.REM *.TXT")]
    )
    if not arquivo:
        return

    titulos = []
    try:
        with open(arquivo, "r", encoding="latin-1") as f:
            for linha in f:
                if not linha.startswith("1"):
                    continue
                try:
                    l = linha.rstrip("\r\n")

                    documento_raw  = l[110:120]                      # 111–120
                    vencimento_str = l[120:126]                      # 121–126
                    valor_str      = l[126:139]                      # 127–139
                    emissao_str    = l[150:156]                      # 151–156

                    tipo_insc_raw  = l[218:220]                      # 219–220
                    doc_raw        = l[220:234]                      # 221–234
                    nome_sacado    = l[234:274].strip()              # 235–274
                    endereco       = l[274:314].strip()              # 275–314
                    cep_raw        = l[326:334]                      # 327–334

                    vencimento = datetime.strptime(vencimento_str, "%d%m%y").strftime("%d/%m/%Y")
                    emissao    = datetime.strptime(emissao_str, "%d%m%y").strftime("%d/%m/%Y")
                    valor      = f"{int(valor_str) / 100:.2f}".replace(".", ",")

                    numero  = documento_raw[:5].strip().zfill(5)
                    parcela = documento_raw[5:].strip().zfill(3)
                    documento_formatado = f"{numero}/{parcela}"

                    doc_tipo = _normalize_tipo_insc(tipo_insc_raw)
                    doc_nums = _digits(doc_raw)

                    if doc_tipo == "01":
                        sacado_doc = doc_nums[-11:].rjust(11, "0")
                    else:
                        sacado_doc = doc_nums[-14:].rjust(14, "0")

                    nosso_numero = gerar_nosso_numero(parametros)

                    titulos.append({
                        "origem": "cnab_bradesco",
                        "sacado": nome_sacado,
                        "documento": documento_formatado,
                        "valor": valor,
                        "vencimento": vencimento,
                        "emissao": emissao,
                        "nosso_numero": nosso_numero,
                        "sacado_cnpj": sacado_doc,
                        "sacado_endereco": endereco,
                        "sacado_cep": _digits(cep_raw),
                        "doc_pagador_tipo": doc_tipo,
                    })
                except Exception:
                    continue
    except Exception as e:
        messagebox.showerror("Erro", f"Falha ao ler o arquivo: {e}")
        return

    if not titulos:
        messagebox.showinfo("Aviso", "Nenhum título encontrado no arquivo selecionado.")
        return

    gerar_remessa_e_zip(titulos, parametros)