# src/retorno_bmp.py
import os, json, tkinter as tk
from tkinter import ttk, filedialog, messagebox

# --- util: carrega config.json
def _load_cfg():
    cfg_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "config.json"))
    try:
        with open(cfg_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _ddmmaa(s):  # "DDMMAA" -> "DD/MM/AAAA"
    s = (s or "").strip()
    if len(s) == 6:
        return f"{s[0:2]}/{s[2:4]}/20{s[4:6]}"
    return ""

def _money13(s):  # 13 dígitos sem ponto -> float/str "9.999,99"
    try:
        v = int((s or "0").strip())/100.0
        return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"

# --- mapeia ocorrência -> status legível
def _status(ocorr, motivos):
    m = motivos.replace(" ", "")
    mapa = {
        "02": "Entrada confirmada",
        "03": "Entrada rejeitada",
        "06": "Liquidado",
        "09": "Baixado",
        "10": "Baixado",
        "12": "Abatimento concedido",
        "13": "Abatimento cancelado",
        "14": "Vencimento alterado",
        "17": "Liquidado após baixa",
        "23": "Encaminhado a cartório",
        "24": "Retirado de cartório",
        "27": "Baixa rejeitada",
        "32": "Instrução rejeitada",
        "34": "Valor do título alterado",
    }
    base = mapa.get(ocorr, f"Ocorrência {ocorr}")
    return f"{base}{(' • Motivos ' + m) if m else ''}"

# --- parser do retorno BMP (CNAB 400) - registro tipo '1'
def parse_retorno_bmp(file_path):
    itens = []
    with open(file_path, "r", encoding="latin-1") as f:
        for line in f:
            if not line or line[0] != "1":
                continue
            controle = line[37:52].strip()          # 38-52 Nº controle do participante
            ocorr    = line[108:110]                # 109-110 Identificação de Ocorrência
            numdoc   = line[116:126].strip()        # 117-126 Nº Documento
            venc     = _ddmmaa(line[146:152])       # 147-152 Vencimento
            valor    = _money13(line[152:165])      # 153-165 Valor do Título
            motivos  = line[318:328].strip()        # 319-328 Motivos
            itens.append({
                "sacado": controle or "(controle)",
                "numdoc": numdoc,
                "venc": venc,
                "valor": valor,
                "status": _status(ocorr, motivos)
            })
    return itens

# --- GUI: abre diálogo, lê arquivo e mostra grade em uma janela (com aba interna)
def abrir_retorno_bmp_gui(root):
    cfg = _load_cfg()
    base = cfg.get("pasta_retorno_nasapay") or cfg.get("pasta_importar_remessa") or os.path.expanduser("~")
    path = filedialog.askopenfilename(
        parent=root,
        initialdir=base,
        title="Selecione o arquivo de Retorno (.RET)",
        filetypes=[("Arquivos de Retorno", "*.ret;*.RET;*.txt"), ("Todos", "*.*")]
    )
    if not path:
        return
    try:
        itens = parse_retorno_bmp(path)
        if not itens:
            messagebox.showwarning("Retorno", "Nenhum registro de transação (tipo 1) encontrado.")
            return
    except Exception as e:
        messagebox.showerror("Retorno", f"Falha ao ler o retorno:\n{e}")
        return

    # Janela com Notebook (aba interna) – não mexe nas suas abas principais
    win = tk.Toplevel(root)
    win.title(f"Retorno Nasapay • {os.path.basename(path)}")
    win.geometry("900x520")

    nb = ttk.Notebook(win)
    nb.pack(fill="both", expand=True)

    frm = ttk.Frame(nb)
    nb.add(frm, text="Títulos retornados")

    tv = ttk.Treeview(frm, columns=("sacado", "numdoc", "venc", "valor", "status"), show="headings", height=18)
    tv.heading("sacado", text="Sacado")
    tv.heading("numdoc", text="Nº Documento")
    tv.heading("venc",   text="Vencimento")
    tv.heading("valor",  text="Valor")
    tv.heading("status", text="Status")

    # larguras enxutas para caber bem
    tv.column("sacado", width=200, anchor="w")
    tv.column("numdoc", width=120, anchor="center")
    tv.column("venc",   width=100, anchor="center")
    tv.column("valor",  width=120, anchor="e")
    tv.column("status", width=300, anchor="w")
    tv.pack(fill="both", expand=True)

    for it in itens:
        tv.insert("", "end", values=(it["sacado"], it["numdoc"], it["venc"], it["valor"], it["status"]))

    btns = ttk.Frame(win)
    btns.pack(fill="x", side="bottom")
    ttk.Button(btns, text="Fechar", command=win.destroy).pack(side="right", padx=8, pady=8)
