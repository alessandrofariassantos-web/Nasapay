# src/retorno_to_bradesco400.py
import os, json, datetime, tkinter as tk
from tkinter import filedialog, messagebox

# ---------- helpers de configuração/beneficiário ----------

def _load_cfg():
    try:
        from utils.parametros import carregar_parametros, salvar_parametros
    except Exception:
        from parametros import carregar_parametros, salvar_parametros  # type: ignore
    return carregar_parametros(), salvar_parametros

def _last_meta(rem_dir: str):
    """Retorna dict lido do .meta.json mais recente em rem_dir (ou None)."""
    try:
        metas = [os.path.join(rem_dir, f) for f in os.listdir(rem_dir) if f.lower().endswith(".meta.json")]
        if not metas: return None
        metas.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        with open(metas[0], "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def _benef_from_meta_or_cfg(cfg: dict):
    """
    Monta o dicionário com os dados do beneficiário:
    prioridade: .meta.json da última remessa -> cfg (config.json).
    """
    meta = _last_meta(cfg.get("pasta_saida") or r"C:/nasapay/remessas") or {}

    def pick(*keys, default=""):
        for k in keys:
            v = (meta.get(k) or cfg.get(k) or "").strip()
            if v: return v
        return default

    benef = {
        "banco": pick("banco", default="237"),
        "nome_banco": pick("nome_banco", default="BRADESCO"),
        "nome_empresa": pick("nome_empresa", "razao_social"),
        "codigo_empresa": pick("codigo_empresa", "codigo_beneficiario", "codigo_cedente"),
        "agencia": pick("agencia"),
        "conta": pick("conta"),
        "dv_conta": pick("dv_conta", "digito"),
        "carteira": pick("carteira"),
        "sequencial_arquivo": pick("sequencial_arquivo", "seq_retorno_bradesco", default="1"),
        "data_gravacao": pick("data_gravacao"),
    }

    # normalizações
    benef["agencia"]  = "".join(ch for ch in benef["agencia"] if ch.isdigit()).zfill(4) if benef["agencia"] else "0000"
    benef["conta"]    = "".join(ch for ch in benef["conta"]   if ch.isdigit()).zfill(7) if benef["conta"]   else "0000000"
    benef["dv_conta"] = (benef["dv_conta"] or "0")[:1]
    benef["carteira"] = "".join(ch for ch in benef["carteira"] if ch.isdigit()).zfill(2) if benef["carteira"] else "00"
    benef["codigo_empresa"] = (benef["codigo_empresa"] or "").ljust(20)[:20]

    if not benef["data_gravacao"]:
        today = datetime.date.today()
        benef["data_gravacao"] = today.strftime("%d%m%y")

    try:
        benef["sequencial_arquivo"] = int(str(benef["sequencial_arquivo"]).strip() or "1")
    except Exception:
        benef["sequencial_arquivo"] = 1

    return benef

def _bump_seq_retorno(cfg: dict, salvar_parametros):
    """Incrementa seq_retorno_bradesco no config.json."""
    try:
        cur = int(str(cfg.get("seq_retorno_bradesco") or "0"))
    except Exception:
        cur = 0
    cfg["seq_retorno_bradesco"] = cur + 1
    try:
        salvar_parametros(cfg)
    except Exception:
        pass

# ---------- parser simples do retorno BMP (.RET) ----------

_DOC_SLICE   = (108, 119)
_VCTO_SLICE  = (146, 154)
_VALOR_SLICE = (154, 167)
_STATUS_SLICE= (318, 329)
_SACADO_SLICE= (46, 86)

def _slice_try(line: str, a: int, b: int) -> str:
    s = line[a:b]
    if not s.strip() and b+1 <= len(line):
        s = line[a+1:b+1]
    return s

def _fmt_valor(num_str: str) -> str:
    d = "".join(ch for ch in (num_str or "") if ch.isdigit())
    if not d: return "0,00"
    v = int(d) / 100.0
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _parse_bmp_retorno(path: str):
    itens = []
    with open(path, "r", encoding="latin-1", errors="ignore") as f:
        for line in f:
            if len(line) < 330:
                continue
            tipo = line[0]
            if tipo not in ("1", "2", "7"):
                continue
            doc   = _slice_try(line, *_DOC_SLICE).strip()
            vcto  = _slice_try(line, *_VCTO_SLICE).strip()
            valor = _slice_try(line, *_VALOR_SLICE).strip()
            stat  = _slice_try(line, *_STATUS_SLICE).strip()
            sac   = _slice_try(line, *_SACADO_SLICE).strip()
            if len(vcto) == 8 and vcto.isdigit():
                vcto = f"{vcto[0:2]}/{vcto[2:4]}/{vcto[4:8]}"
            valor = _fmt_valor(valor)
            itens.append({"sacado": sac, "doc": doc, "venc": vcto, "valor": valor, "status": stat})
    return itens

# ---------- gerador de arquivo Retorno Bradesco 400 ----------

def _header_retorno_bradesco(benef):
    line = [" "] * 400
    line[0] = "0"
    line[1:9]   = list("RETORNO ")
    line[26:46] = list(benef["codigo_empresa"])
    nome = (benef["nome_empresa"] or "").ljust(30)[:30]
    line[46:76] = list(nome)
    line[76:79] = list("237")
    line[79:94] = list("BRADESCO       ")
    line[94:100]= list(benef["data_gravacao"])
    seq = str(benef["sequencial_arquivo"]).zfill(7)
    line[394:400]= list(seq)
    return "".join(line)

def _trailer_retorno_bradesco(total_registros: int):
    line = [" "] * 400
    line[0] = "9"
    line[394:400] = list(str(total_registros).zfill(6)[:6])
    return "".join(line)

def _detail_retorno_bradesco(item, benef):
    line = [" "] * 400
    line[0] = "1"
    doc = (item.get("doc") or "")[:12].rjust(12)
    line[37:49] = list(doc)
    nn = "".ljust(8)
    line[62:70] = list(nn)
    try:
        dd, mm, aaaa = item.get("venc","").split("/")
        line[146:152] = list(dd+mm+aaaa[-2:])
    except Exception:
        pass
    v = "".join(ch for ch in (item.get("valor") or "") if ch.isdigit())
    v = v.zfill(13)[-13:]
    line[152:165] = list(v)
    line[170:174] = list(benef["agencia"])
    ccc = (benef["conta"] + benef["dv_conta"])[:8].rjust(8)
    line[174:182] = list(ccc)
    line[106:108] = list(benef["carteira"])
    oc = (item.get("status") or "")[:10].rjust(10)
    line[318:328] = list(oc)
    return "".join(line)

def converter_bmp_para_bradesco400(parent=None):
    """
    1) pergunta o .RET do BMP
    2) lê e exibe contagem
    3) gera arquivo de retorno CNAB 400 (Bradesco) na Pasta Retorno Nasapay
    """
    cfg, salvar_parametros = _load_cfg()

    # >>> abre na pasta configurada para retorno
    dir_retorno_ini = (
        cfg.get("pasta_retorno_nasapay")
        or cfg.get("pasta_retorno")   # retrocompatível
        or os.path.expanduser("~")
    )

    path = filedialog.askopenfilename(
        parent=parent,
        initialdir=dir_retorno_ini,
        title="Selecione o arquivo de retorno BMP (.RET)",
        filetypes=[("Retorno BMP", "*.ret;*.RET"), ("Todos", "*.*")]
    )
    if not path:
        return

    itens = _parse_bmp_retorno(path)
    if not itens:
        messagebox.showerror("Retorno Nasapay", "Não encontrei registros de detalhe nesse arquivo.", parent=parent)
        return

    benef = _benef_from_meta_or_cfg(cfg)

    # >>> saída definida por “Pasta Retorno Nasapay”
    out_dir = (
        cfg.get("pasta_retorno_nasapay")
        or cfg.get("pasta_retorno")       # retrocompatível
        or r"C:/nasapay/retornos"
    )
    try:
        os.makedirs(out_dir, exist_ok=True)
    except Exception:
        pass

    base = os.path.splitext(os.path.basename(path))[0]
    out_path = os.path.join(out_dir, f"RET_BRADESCO_{base}.ret")

    lines = []
    lines.append(_header_retorno_bradesco(benef))
    for it in itens:
        lines.append(_detail_retorno_bradesco(it, benef))
    lines.append(_trailer_retorno_bradesco(len(lines)+1))

    with open(out_path, "w", encoding="latin-1", errors="ignore") as f:
        for ln in lines:
            s = (ln or "")[:400].ljust(400)
            f.write(s + "\r\n")

    _bump_seq_retorno(cfg, salvar_parametros)

    messagebox.showinfo(
        "Retorno convertido",
        f"Registros convertidos: {len(itens)}\nArquivo gerado:\n{out_path}",
        parent=parent
    )
