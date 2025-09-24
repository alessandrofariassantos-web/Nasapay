# utils/sacador_avalista.py
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import font as tkfont
import re

from utils import store, session

# ------------ helpers ------------
def _only_digits(s: str | None) -> str:
    return re.sub(r"\D", "", s or "")

def _fmt_cnpj_mask(cnpj: str | None) -> str:
    d = _only_digits(cnpj)
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}" if len(d) == 14 else (cnpj or "")

def _enforce_upper(var: tk.StringVar):
    def _cb(*_):
        v = (var.get() or "").upper()
        if v != var.get():
            var.set(v)
    var.trace_add("write", _cb)

def _bind_cnpj_mask(entry: ttk.Entry, var: tk.StringVar):
    """
    Máscara de CNPJ com o cursor preservado no lugar “lógico” (quantidade de dígitos).
    Não preenche zeros: apenas formata o que o usuário digitar.
    """
    guard = {"on": False}

    def _on_key(_=None):
        if guard["on"]:
            return
        guard["on"] = True
        try:
            s = var.get()
            # posição atual do cursor e quantos dígitos existem antes dele
            idx = entry.index("insert")
            digits_before = sum(1 for ch in s[:idx] if ch.isdigit())

            d = _only_digits(s)[:14]

            # aplica máscara progressiva
            out = d
            if len(d) > 2:
                out = d[:2] + "." + d[2:]
            if len(d) > 5:
                out = d[:2] + "." + d[2:5] + "." + d[5:]
            if len(d) > 8:
                out = d[:2] + "." + d[2:5] + "." + d[5:8] + "/" + d[8:]
            if len(d) > 12:
                out = d[:2] + "." + d[2:5] + "." + d[5:8] + "/" + d[8:12] + "-" + d[12:14]

            if out != s:
                var.set(out)
                # recoloca o cursor após a mesma quantidade de dígitos
                cnt = 0
                new_idx = len(out)
                for i, ch in enumerate(out):
                    if ch.isdigit():
                        cnt += 1
                    if cnt >= digits_before:
                        new_idx = i + 1
                        break
                entry.icursor(new_idx)
        finally:
            guard["on"] = False

    entry.bind("<KeyRelease>", _on_key)

# ------------ autosize Treeview ------------
def _autosize_columns(tree: ttk.Treeview, min_px: int = 60, pad: int = 24):
    f = tkfont.nametofont("TkDefaultFont")
    cols = tree["columns"]
    for c in cols:
        # impede esticar para ocupar toda a janela
        tree.column(c, stretch=False)
        w = f.measure(tree.heading(c, "text"))
        for iid in tree.get_children(""):
            w = max(w, f.measure(str(tree.set(iid, c))))
        tree.column(c, width=max(min_px, w + pad))

# ------------ janela de edição ------------
def _open_editor(parent: tk.Misc, eid: int, on_saved, sid: int | None = None):
    con = store._connect()
    try:
        data = {"id": None, "razao": "", "cnpj": ""}
        if sid is not None:
            r = store.sac_get(con, eid, sid)
            if r:
                data["id"] = int(r["id"])
                data["razao"] = r["razao"] or ""
                data["cnpj"] = _fmt_cnpj_mask(r["cnpj"] or "")
    finally:
        con.close()

    win = tk.Toplevel(parent)
    win.title("Editar Sacador/Avalista" if sid else "Novo Sacador/Avalista")
    win.transient(parent)
    win.grab_set()

    frm = ttk.Frame(win)
    frm.pack(fill="both", expand=True, padx=10, pady=8)

    ttk.Label(frm, text="Razão Social").grid(row=0, column=0, sticky="e", padx=6, pady=4)
    v_razao = tk.StringVar(value=data["razao"])
    _enforce_upper(v_razao)
    e_razao = ttk.Entry(frm, textvariable=v_razao, width=42)
    e_razao.grid(row=0, column=1, sticky="w", padx=6, pady=4)

    ttk.Label(frm, text="CNPJ").grid(row=1, column=0, sticky="e", padx=6, pady=4)
    v_cnpj = tk.StringVar(value=data["cnpj"])
    e_cnpj = ttk.Entry(frm, textvariable=v_cnpj, width=20)
    e_cnpj.grid(row=1, column=1, sticky="w", padx=6, pady=4)
    _bind_cnpj_mask(e_cnpj, v_cnpj)

    btns = ttk.Frame(frm)
    btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(6, 2))

    def _salvar():
        raz = (v_razao.get() or "").strip().upper()
        if not raz:
            messagebox.showwarning("Sacador/Avalista", "Informe a Razão Social.", parent=win)
            return
        cnpj = _only_digits(v_cnpj.get())
        con = store._connect()
        try:
            store.sac_upsert(con, eid, id=data["id"], razao=raz, cnpj=cnpj)
            messagebox.showinfo("Sacador/Avalista", "Registro salvo.", parent=win)
            win.destroy()
            on_saved()
        except Exception as e:
            messagebox.showerror("Sacador/Avalista", f"Falha ao salvar:\n{e}", parent=win)
        finally:
            con.close()

    ttk.Button(btns, text="Salvar", command=_salvar).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Fechar", command=win.destroy).pack(side="right")

    e_razao.focus_set()

# ------------ tela principal ------------
def open_sacador_avalista(parent=None, container: ttk.Notebook | None = None):
    eid = session.get_empresa_id()
    if not eid:
        messagebox.showwarning("Sacador/Avalista", "Selecione uma empresa ativa.", parent=parent)
        return

    if container is None:
        win = tk.Toplevel(parent)
        win.title("Sacador/Avalista")
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
    else:
        nb = container

    page = ttk.Frame(nb)
    nb.add(page, text="Sacador/Avalista")
    nb.select(page)

    cols = ("id", "razao", "cnpj")
    tree = ttk.Treeview(page, columns=cols, show="headings", height=16)
    vsb = ttk.Scrollbar(page, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    page.rowconfigure(0, weight=1)
    page.columnconfigure(0, weight=1)

    tree.heading("id", text="ID")
    tree.heading("razao", text="Razão Social")
    tree.heading("cnpj", text="CNPJ")

    tree.column("id", anchor="center")
    tree.column("razao", anchor="w")
    tree.column("cnpj", anchor="center")

    def _refresh():
        for i in tree.get_children(""):
            tree.delete(i)
        con = store._connect()
        try:
            rows = store.sac_list(con, eid)
            for r in rows:
                tree.insert(
                    "",
                    "end",
                    iid=str(r["id"]),
                    values=(r["id"], r["razao"], _fmt_cnpj_mask(r["cnpj"])),
                )
        finally:
            con.close()
        _autosize_columns(tree)

    def _sel_id():
        s = tree.selection()
        return int(tree.item(s[0], "values")[0]) if s else None

    def _novo():
        _open_editor(page, eid, _refresh, sid=None)

    def _editar():
        sid = _sel_id()
        if sid is None:
            messagebox.showwarning("Sacador/Avalista", "Selecione um registro.", parent=page)
            return
        _open_editor(page, eid, _refresh, sid=sid)

    def _excluir():
        sid = _sel_id()
        if sid is None:
            messagebox.showwarning("Sacador/Avalista", "Selecione um registro.", parent=page)
            return
        if not messagebox.askyesno("Excluir", "Confirma exclusão?", parent=page):
            return
        con = store._connect()
        try:
            store.sac_delete(con, eid, sid)
        finally:
            con.close()
        _refresh()

    # botões todos à direita
    btns = ttk.Frame(page)
    btns.grid(row=1, column=0, columnspan=2, sticky="e", pady=(6, 6))
    ttk.Button(btns, text="Fechar", command=lambda: nb.forget(page)).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Excluir", command=_excluir).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Editar", command=_editar).pack(side="right", padx=(6, 0))
    ttk.Button(btns, text="Novo", command=_novo).pack(side="right", padx=(6, 0))

    tree.bind("<Double-1>", lambda e: _editar())
    _refresh()
