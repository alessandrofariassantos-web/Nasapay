# utils/popup_confirmacao.py
import re
import tkinter as tk
from tkinter import ttk

# ---------- helpers de valor ----------
def _parse_brl(v) -> float:
    s = str(v or "").strip().replace(" ", "")
    if s == "":
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        digits = re.sub(r"\D", "", s)
        if not digits:
            return 0.0
        return float(int(digits)) / 100.0

def _fmt_brl(x: float) -> str:
    try:
        f = float(x)
    except Exception:
        f = 0.0
    txt = f"{f:,.2f}"
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")

# ---------- centralização ----------
def _center_on_parent(top: tk.Toplevel, parent):
    try:
        top.update_idletasks()
        if parent is None: parent = top.winfo_toplevel()
        px = parent.winfo_rootx(); py = parent.winfo_rooty()
        pw = parent.winfo_width(); ph = parent.winfo_height()
        tw = top.winfo_width(); th = top.winfo_height()
        x = px + (pw - tw)//2; y = py + (ph - th)//2
        top.geometry(f"+{max(0,x)}+{max(0,y)}")
        top.transient(parent); top.grab_set(); top.focus_force()
    except Exception:
        try: top.grab_set()
        except Exception: pass

# ---------- popup ----------
def popup_confirmacao_titulos(titulos: list[dict], parent=None):
    """
    Mostra uma listagem dos títulos gerados com TOTAL em R$ e QTD de títulos.
    Colunas na ordem: #, Sacado, Documento, Vencimento, Valor (R$).
    """
    total = 0.0
    for t in titulos or []:
        total += _parse_brl(t.get("valor", "0"))

    top = tk.Toplevel(parent)
    top.title("Confirmação dos Títulos Gerados")
    top.minsize(720, 380)

    # layout base
    top.columnconfigure(0, weight=1)
    top.rowconfigure(0, weight=1)

    frame = ttk.Frame(top)
    frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    cols = ("idx", "sacado", "documento", "vencimento", "valor")
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
    vbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hbar = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscroll=vbar.set, xscroll=hbar.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vbar.grid(row=0, column=1, sticky="ns")
    hbar.grid(row=1, column=0, sticky="ew")

    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)

    tree.heading("idx",         text="#")
    tree.heading("sacado",      text="Sacado")
    tree.heading("documento",   text="Documento")
    tree.heading("vencimento",  text="Vencimento")
    tree.heading("valor",       text="Valor (R$)")

    tree.column("idx",        width=50,  anchor="e",      stretch=False)
    tree.column("sacado",     width=340, anchor="w",      stretch=True)
    tree.column("documento",  width=150, anchor="w",      stretch=True)
    tree.column("vencimento", width=110, anchor="center", stretch=False)
    tree.column("valor",      width=120, anchor="e",      stretch=False)

    for i, t in enumerate(titulos or [], start=1):
        sac  = str(t.get("sacado", "") or "")
        doc  = str(t.get("documento", "") or "")
        venc = str(t.get("vencimento", "") or "")
        val  = _fmt_brl(_parse_brl(t.get("valor", "0")))
        tree.insert("", "end", values=(f"{i:03d}", sac, doc, venc, val))

    footer = ttk.Frame(top)
    footer.grid(row=1, column=0, sticky="ew", padx=10, pady=(6, 10))
    footer.columnconfigure(0, weight=1)
    footer.columnconfigure(1, weight=0)

    total_txt = f"TOTAL — R$: {_fmt_brl(total)}"
    qtd_txt   = f"QTD Total: {len(titulos):03d}"

    lbl_total = ttk.Label(footer, text=total_txt, font=("Segoe UI", 10, "bold"))
    lbl_qtd   = ttk.Label(footer, text=qtd_txt,   font=("Segoe UI", 10))

    lbl_total.grid(row=0, column=0, sticky="w")
    lbl_qtd.grid(row=0, column=1, sticky="e", padx=(10, 0))

    actions = ttk.Frame(top)
    actions.grid(row=2, column=0, sticky="e", padx=10, pady=(0, 10))

    def fechar():
        try:
            top.grab_release()
        except Exception:
            pass
        top.destroy()

    ttk.Button(actions, text="OK", command=fechar).pack(side="right")

    # centraliza e ativa
    _center_on_parent(top, parent)

    # atalho ESC para fechar
    top.bind("<Escape>", lambda e: fechar())
