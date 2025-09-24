# src/conversor_xml.py
import os
import xml.etree.ElementTree as ET
from datetime import datetime
from tkinter import filedialog, messagebox

from utils.parametros import carregar_parametros, gerar_nosso_numero
from utils.gerar_remessa import gerar_remessa_e_zip

def converter_arquivo_xml():
    parametros = carregar_parametros() or {}
    caminho_entrada = (
        parametros.get("pasta_importar_remessa")
        or parametros.get("pasta_entrada")
        or os.path.expanduser("~")
    )

    arquivos = filedialog.askopenfilenames(
        initialdir=caminho_entrada,
        filetypes=[("Arquivos XML", "*.xml")]
    )
    if not arquivos:
        return

    titulos = []
    for arq in arquivos:
        try:
            tree = ET.parse(arq)
            root = tree.getroot()
            ns = {"nfe": "http://www.portalfiscal.inf.br/nfe"}

            duplicatas = root.findall(".//nfe:dup", namespaces=ns)
            if not duplicatas:
                continue

            ide = root.find(".//nfe:ide", namespaces=ns)
            dest = root.find(".//nfe:dest", namespaces=ns)

            nfe_num = ide.findtext("nfe:nNF", default="", namespaces=ns)
            emissao_raw = (ide.findtext("nfe:dhEmi", default="", namespaces=ns) or "")[:10]
            emissao = datetime.strptime(emissao_raw, "%Y-%m-%d").strftime("%d/%m/%Y")

            sacado_nome = dest.findtext("nfe:xNome", default="", namespaces=ns) or ""
            doc_sacado  = (dest.findtext("nfe:CNPJ", default="", namespaces=ns)
                           or dest.findtext("nfe:CPF", default="", namespaces=ns) or "")
            end = dest.find(".//nfe:enderDest", namespaces=ns)

            xLgr = end.findtext("nfe:xLgr","",namespaces=ns) or ""
            nro  = end.findtext("nfe:nro","",namespaces=ns) or ""
            xBai = end.findtext("nfe:xBairro","",namespaces=ns) or ""
            cep  = end.findtext("nfe:CEP","",namespaces=ns) or ""
            endereco_str = f"{xLgr}, {nro} - {xBai}".strip().strip(", -")

            for dup in duplicatas:
                parcela = dup.findtext("nfe:nDup", default="", namespaces=ns) or ""
                venc_raw = dup.findtext("nfe:dVenc", default="", namespaces=ns) or ""
                vencimento = datetime.strptime(venc_raw, "%Y-%m-%d").strftime("%d/%m/%Y")
                valor = dup.findtext("nfe:vDup", default="0,00", namespaces=ns) or "0,00"

                nosso_numero = gerar_nosso_numero(parametros)

                dig = "".join(ch for ch in doc_sacado if ch.isdigit())
                tipo = "02" if len(dig) == 14 else "01"

                titulos.append({
                    "sacado": sacado_nome,
                    "documento": f"{nfe_num}-{parcela}" if parcela else nfe_num,
                    "valor": valor,
                    "vencimento": vencimento,
                    "nosso_numero": nosso_numero,
                    "sacado_endereco": endereco_str,
                    "sacado_cep": "".join(ch for ch in (cep or "") if ch.isdigit()),
                    "doc_pagador_tipo": tipo,
                    "emissao": emissao,
                    "sacado_cnpj": dig
                })

        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao processar {arq}: {str(e)}")

    if not titulos:
        messagebox.showinfo("Aviso", "Nenhum título válido encontrado nos arquivos selecionados.")
        return

    gerar_remessa_e_zip(titulos, parametros)