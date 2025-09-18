# src/remessa_meta.py
import os, json, re

def record_remessa_meta(rem_path: str):
    """
    Lê o header da remessa Bradesco 400 e grava um .meta.json com os campos
    essenciais para montagem do retorno (código empresa, agência/conta, carteira, etc.).
    """
    try:
        with open(rem_path, "r", encoding="latin-1") as f:
            header = f.readline()
        if not header or header[0] not in "01":  # cabeçalho 0/1 conforme layout
            return
        meta = {
            "banco": header[76:79].strip() or "237",
            "nome_banco": header[79:94].strip() or "BRADESCO",
            "data_gravacao": header[94:100].strip(),
            "codigo_empresa": header[26:46],   # 20 posições (ver seu layout de remessa)
            "nome_empresa": header[46:76].strip(),
            # Se sua remessa grava agência/conta/carteira em outras posições, ajuste aqui:
            "agencia": "",
            "conta": "",
            "dv_conta": "",
            "carteira": ""
        }
        meta_path = rem_path + ".meta.json"
        with open(meta_path, "w", encoding="utf-8") as g:
            json.dump(meta, g, ensure_ascii=False, indent=2)
    except Exception:
        pass
