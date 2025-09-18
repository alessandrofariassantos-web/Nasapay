# utils/contas_bancarias.py
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
import re

from utils import store, session

# ---------- helpers ----------
def _digits(s: str | None, limit: int | None = None) -> str:
    s = re.sub(r"\D", "", s or "")
    return s[:limit] if limit else s

def _bind_digits(entry: ttk.Entry, var: tk.StringVar, limit: int):
    """
    Permite apenas dígitos e limita a quantidade, preservando a posição do cursor.
    Não preenche zeros à esquerda.
    """
    guard = {"on": False}

    def _on_key(_=None):
        if guard["on"]:
            return
        guard["on"] = True
        try:
            s = var.get()
            idx = entry.index("insert")
            digits_before = sum(1 for ch in s[:idx] if ch.isdigit())

            raw = _digits(s, limit)
            if raw != s:
                var.set(raw)
                # recoloca o cursor após o mesmo nº de dígitos
                cnt = 0
                new_idx = len(raw)
                for i, ch in enumerate(raw):
                    if ch.isdigit():
                        cnt += 1
                    if cnt >= digits_before:
                        new_idx = i + 1
                        break
                entry.icursor(new_idx)
        finally:
            guard["on"] = False

    entry.bind("<KeyRelease>", _on_key)

def _autosize_columns(tree: ttk.Treeview, min_px=60, pad=24):
    f = tkfont.nametofont("TkDefaultFont")
    cols = tree["columns"]
    for c in cols:
        tree.column(c, stretch=False)  # impede “esticar” para ocupar toda a largura
        w = f.measure(tree.heading(c, "text"))
        for iid in tree.get_children(""):
            w = max(w, f.measure(str(tree.set(iid, c))))
        tree.column(c, width=max(min_px, w + pad))

# ---------- editor ----------
def _open_editor(parent: tk.Misc, eid: int, on_saved, cid: int | None = None):
    data = {
        "id": None,
        "isp": "",
        "banco": "",
        "agencia": "",
        "dv_agencia": "",
        "conta": "",
        "dv_conta": "",
        "carteira": "",
        "convenio": "",
    }
    con = store._connect()
    try:
        if cid is not None:
            r = store.cb_get(con, eid, cid)
            if r:
                data.update({k: (r[k] or "") for k in data if k in r.keys()})
                data["id"] = int(r["id"])
    finally:
        con.close()

    win = tk.Toplevel(parent)
    win.title("Editar Conta" if cid else "Nova Conta")
    win.transient(parent)
    win.grab_set()

    frm = ttk.Frame(win)
    frm.pack(fill="both", expand=True, padx=10, pady=8)

    def _linha(r, label, var, w):
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky="e", padx=6, pady=3)
        e = ttk.Entry(frm, textvariable=var, width=w)
        e.grid(row=r, column=1, sticky="w", padx=6, pady=3)
        return e

    v_isp = tk.StringVar(value=data["isp"])
    e_isp = _linha(0, "ISP", v_isp, 6)
    _bind_digits(e_isp, v_isp, 3)

    v_bco = tk.StringVar(value=(data["banco"] or "").upper())
    e_bco = _linha(1, "Banco", v_bco, 32)

    def _upper(*_):
        v_bco.set((v_bco.get() or "").upper())

    v_bco.trace_add("write", _upper)

    v_ag = tk.StringVar(value=data["agencia"])
    e_ag = _linha(2, "Agência", v_ag, 8)
    _bind_digits(e_ag, v_ag, 4)

    v_dva = tk.StringVar(value=data["dv_agencia"])
    e_dva = _linha(3, "DV Ag.", v_dva, 4)
    _bind_digits(e_dva, v_dva, 1)

    v_cta = tk.StringVar(value=data["conta"])
    e_cta = _linha(4, "Conta", v_cta, 20)
    _bind_digits(e_cta, v_cta, 15)

    v_dvc = tk.StringVar(value=data["dv_conta"])
    e_dvc = _linha(5, "DV Cta.", v_dvc, 4)
    _bind_digits(e_dvc, v_dvc, 1)

    v_cart = tk.StringVar(value=data["carteira"])
    e_cart = _linha(6, "Carteira", v_cart, 6)
    _bind_digits(e_cart, v_cart, 3)

    v_conv = tk.StringVar(value=data["convenio"])
    e_conv = _linha(7, "Convênio", v_conv, 20)
    _bind_digits(e_conv, v_conv, 15)

    btns = ttk.Frame(frm)
    btns.grid(row=8, column=0, columnspan=2, sticky="e", pady=(6, 2))

    def _salvar():
        con = store._connect()
        try:
            store.cb_upsert(
                con,
                eid,
                id=data["id"],
                isp=v_isp.get(),
                banco=v_bco.get(),
                agencia=v_ag.get(),
                dv_agencia=v_dva.get(),
                conta=v_cta.get(),
                dv_conta=v_dvc.get(),
                carteira=v_cart.get(),
                convenio=v_conv.get(),
            )
            messagebox.showinfo("Contas Bancárias", "Registro salvo.", parent=win)
            win.destroy()
            on_saved()
        except Exception as e:
            messagebox.showerror("Contas Bancárias", f"Falha ao salvar:\n{e}", parent=win)
        finally:
            con.close()

    ttk.Button(btns, text="Salvar", command=_salvar).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Fechar", command=win.destroy).pack(side="right")
    e_isp.focus_set()

# ---------- tela principal ----------
def open_contas(parent=None, container: ttk.Notebook | None = None):
    eid = session.get_empresa_id()
    if not eid:
        messagebox.showwarning("Contas Bancárias", "Selecione uma empresa ativa.", parent=parent)
        return

    if container is None:
        win = tk.Toplevel(parent)
        win.title("Contas Bancárias")
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
    else:
        nb = container

    page = ttk.Frame(nb)
    nb.add(page, text="Contas Bancárias")
    nb.select(page)

    cols = (
        "id",
        "isp",
        "banco",
        "agencia",
        "dv_agencia",
        "conta",
        "dv_conta",
        "carteira",
        "convenio",
    )
    tree = ttk.Treeview(page, columns=cols, show="headings", height=16)
    vsb = ttk.Scrollbar(page, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    page.rowconfigure(0, weight=1)
    page.columnconfigure(0, weight=1)

    headers = {
        "id": "ID",
        "isp": "ISP",
        "banco": "Banco",
        "agencia": "Agência",
        "dv_agencia": "DV Ag.",
        "conta": "Conta",
        "dv_conta": "DV Cta.",
        "carteira": "Carteira",
        "convenio": "Convênio",
    }
    for c in cols:
        tree.heading(c, text=headers[c])
        tree.column(c, anchor=("w" if c in ("banco", "convenio") else "center"))

    def _refresh():
        for i in tree.get_children(""):
            tree.delete(i)
        con = store._connect()
        try:
            rows = store.cb_list(con, eid)
            for r in rows:
                vals = (
                    r["id"],
                    r["isp"] or "",
                    r["banco"] or "",
                    r["agencia"] or "",
                    r["dv_agencia"] or "",
                    r["conta"] or "",
                    r["dv_conta"] or "",
                    r["carteira"] or "",
                    r["convenio"] or "",
                )
                tree.insert("", "end", iid=str(r["id"]), values=vals)
        finally:
            con.close()
        _autosize_columns(tree)

    def _sel_id():
        s = tree.selection()
        return int(tree.item(s[0], "values")[0]) if s else None

    def _novo():
        _open_editor(page, eid, _refresh, cid=None)

    def _editar():
        cid = _sel_id()
        if cid is None:
            messagebox.showwarning("Contas Bancárias", "Selecione um registro.", parent=page)
            return
        _open_editor(page, eid, _refresh, cid=cid)

    def _excluir():
        cid = _sel_id()
        if cid is None:
            messagebox.showwarning("Contas Bancárias", "Selecione um registro.", parent=page)
            return
        if not messagebox.askyesno("Excluir", "Confirma exclusão?", parent=page):
            return
        con = store._connect()
        try:
            store.cb_delete(con, eid, cid)
        finally:
            con.close()
        _refresh()

    btns = ttk.Frame(page)
    btns.grid(row=1, column=0, columnspan=2, sticky="e", pady=(6, 6))
    ttk.Button(btns, text="Fechar", command=lambda: nb.forget(page)).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Excluir", command=_excluir).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Editar", command=_editar).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Novo", command=_novo).pack(side="right", padx=(6, 0))

    tree.bind("<Double-1>", lambda e: _editar())
    _refresh()
