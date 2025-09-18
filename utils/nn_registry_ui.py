# === utils/nn_registry_ui.py ===
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont

from . import nn_registry as reg

PADX = 8
PADY = 6

COLS = ("sacado", "documento", "valor", "vencimento",
        "nosso_numero", "arquivo_nome", "timestamp")

HEADERS = {
    "sacado": "Sacado",
    "documento": "Nº do Docto",
    "valor": "Valor",
    "vencimento": "Vencimento",
    "nosso_numero": "Nosso Número",
    "arquivo_nome": "Arquivo gerado",
    "timestamp": "Criado em",
}

ANCHORS = {
    "sacado": "w",
    "documento": "center",
    "valor": "e",
    "vencimento": "center",
    "nosso_numero": "center",
    "arquivo_nome": "w",
    "timestamp": "center",
}

CSV_PATH = reg.REG_PATH

def _open_window(parent: tk.Tk | tk.Toplevel):
    win = tk.Toplevel(parent)
    win.title("Registro de Nosso Número")
    win.geometry("1120x580")
    win.transient(parent)
    win.grab_set()

    # Top
    top = ttk.Frame(win); top.pack(fill="x", padx=PADX, pady=(PADY,0))
    ttk.Label(top, text="Filtro rápido:").pack(side="left")
    ent_filtro = ttk.Entry(top, width=38)
    ent_filtro.pack(side="left", padx=(6,10))

    btn_atualizar = ttk.Button(top, text="Atualizar (F5)")
    btn_export = ttk.Button(top, text="Exportar CSV")
    btn_import = ttk.Button(top, text="Importar CSV")
    btn_edit = ttk.Button(top, text="Editar")
    btn_del = ttk.Button(top, text="Apagar Selecionados")
    btn_open_csv = ttk.Button(top, text="Abrir CSV")
    btn_open_dir = ttk.Button(top, text="Abrir Pasta")

    for b in (btn_atualizar, btn_export, btn_import, btn_edit, btn_del, btn_open_csv, btn_open_dir):
        b.pack(side="left", padx=4)

    # Tabela
    frm = ttk.Frame(win); frm.pack(fill="both", expand=True, padx=PADX, pady=PADY)
    tree = ttk.Treeview(frm, columns=COLS, show="headings", selectmode="extended")
    tree.pack(side="left", fill="both", expand=True)
    vsb = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
    vsb.pack(side="right", fill="y")
    tree.configure(yscrollcommand=vsb.set)

    # Cabeçalhos
    for c in COLS:
        tree.heading(c, text=HEADERS[c])

    # Larguras iniciais (Sacado largo pra ~40 chars)
    tree.column("sacado",       anchor=ANCHORS["sacado"],       stretch=True,  width=360, minwidth=300)
    tree.column("documento",    anchor=ANCHORS["documento"],    stretch=False, width=120, minwidth=90)
    tree.column("valor",        anchor=ANCHORS["valor"],        stretch=False, width=120, minwidth=90)
    tree.column("vencimento",   anchor=ANCHORS["vencimento"],   stretch=False, width=110, minwidth=90)
    tree.column("nosso_numero", anchor=ANCHORS["nosso_numero"], stretch=False, width=140, minwidth=120)
    tree.column("arquivo_nome", anchor=ANCHORS["arquivo_nome"], stretch=True,  width=240, minwidth=180)
    tree.column("timestamp",    anchor=ANCHORS["timestamp"],    stretch=False, width=150, minwidth=120)

    # Fonte para medir (não usa tree.cget('font') pra evitar erro do Tk)
    try:
        treefont = tkfont.nametofont("TkDefaultFont")
    except Exception:
        treefont = tkfont.Font(family="Segoe UI", size=9)

    # Mapa iid -> key (índice real)
    item_key: dict[str, str] = {}

    def autosize_columns(items):
        padding = 24
        for c in COLS:
            header_w = treefont.measure(HEADERS[c]) + padding
            max_w = header_w
            for iid in items:
                val = str(tree.set(iid, c))
                w = treefont.measure(val) + padding
                if w > max_w:
                    max_w = w
            info = tree.column(c)
            minw = int(info.get("minwidth") or 90)
            tree.column(c, width=max(max_w, minw))

    # Status bar
    status = ttk.Label(win, text="", anchor="w")
    status.pack(fill="x", padx=PADX, pady=(0, PADY))
    def set_status(msg: str): status.configure(text=msg)

    def refresh():
        tree.delete(*tree.get_children())
        item_key.clear()
        filtro = ent_filtro.get().strip()
        data = reg.list_entries(filtro=filtro, sort_by="timestamp", reverse=True)
        iids = []
        for row in data:
            values = (
                row.get("sacado", ""),
                row.get("documento", ""),
                row.get("valor", ""),
                row.get("vencimento", ""),
                row.get("nosso_numero", ""),
                os.path.basename(row.get("arquivo", "") or ""),
                row.get("timestamp", ""),
            )
            iid = tree.insert("", "end", values=values)
            item_key[iid] = row.get("key", "")
            iids.append(iid)
        autosize_columns(iids)
        set_status(f"{len(data)} registro(s) — CSV: {CSV_PATH}")

    def on_export():
        path = filedialog.asksaveasfilename(
            parent=win, title="Salvar CSV",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")]
        )
        if not path: return
        n = reg.export_to_csv(path, filtro=ent_filtro.get().strip() or None)
        messagebox.showinfo("Exportação concluída", f"{n} linha(s) exportada(s).", parent=win)

    def on_import():
        path = filedialog.askopenfilename(
            parent=win, title="Importar CSV",
            filetypes=[("CSV", "*.csv"), ("Todos", "*.*")]
        )
        if not path: return
        add, upd, skip = reg.import_from_csv(path)
        messagebox.showinfo("Importação", f"Adicionados: {add}\nAtualizados: {upd}\nIgnorados: {skip}", parent=win)
        refresh()

    def on_delete():
        sel = list(tree.selection())
        if not sel: return
        if not messagebox.askyesno("Confirmar", "Apagar os itens selecionados?", parent=win):
            return
        ids = []
        for iid in sel:
            key = item_key.get(iid)
            if key != "" and key is not None:
                ids.append(int(key))
        apagados = reg.delete_entries(ids)
        messagebox.showinfo("Concluído", f"{apagados} registro(s) apagado(s).", parent=win)
        refresh()

    def on_edit():
        sel = list(tree.selection())
        if not sel: return
        iid = sel[0]
        key = item_key.get(iid)
        if key is None or key == "":
            return
        # Recarrega dados atuais pra esse índice
        data = reg.list_entries(sort_by="timestamp", reverse=True)
        try:
            idx = int(key)
        except:
            idx = None
        # Dialog
        dlg = tk.Toplevel(win); dlg.title("Editar registro"); dlg.transient(win); dlg.grab_set()
        ttk.Label(dlg, text="Nosso Número (11 dígitos):").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        e_nn = ttk.Entry(dlg, width=22); e_nn.grid(row=0, column=1, padx=10, pady=8)
        ttk.Label(dlg, text="Arquivo (caminho completo):").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        e_arq = ttk.Entry(dlg, width=64); e_arq.grid(row=1, column=1, padx=10, pady=8)
        ttk.Label(dlg, text="Sacado (nome):").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        e_sc = ttk.Entry(dlg, width=64); e_sc.grid(row=2, column=1, padx=10, pady=8)
        # Pre-fill usando os valores mostrados na listagem para o iid
        vals = tree.item(iid, "values")
        try:
            e_nn.insert(0, vals[4])
        except: pass
        try:
            e_arq.insert(0, vals[5])
        except: pass
        try:
            e_sc.insert(0, vals[0])
        except: pass

        def _ok():
            try:
                reg.update_entry(key, nosso_numero=e_nn.get().strip(), arquivo=e_arq.get().strip(), sacado=e_sc.get().strip())
            except Exception as ex:
                messagebox.showerror("Erro", str(ex), parent=dlg)
                return
            dlg.destroy()
            refresh()

        ttk.Button(dlg, text="Salvar", command=_ok).grid(row=3, column=1, sticky="e", padx=10, pady=10)
        ttk.Button(dlg, text="Cancelar", command=dlg.destroy).grid(row=3, column=0, sticky="w", padx=10, pady=10)

    def on_open_csv():
        if not os.path.exists(CSV_PATH):
            messagebox.showwarning("Aviso", f"CSV não encontrado em:\n{CSV_PATH}", parent=win)
            return
        try: os.startfile(CSV_PATH)
        except Exception as e: messagebox.showerror("Erro", str(e), parent=win)

    def on_open_dir():
        d = os.path.dirname(CSV_PATH) or "."
        try: os.startfile(d)
        except Exception as e: messagebox.showerror("Erro", str(e), parent=win)

    # binds
    btn_atualizar.configure(command=refresh)
    btn_export.configure(command=on_export)
    btn_import.configure(command=on_import)
    btn_del.configure(command=on_delete)
    btn_edit.configure(command=on_edit)
    btn_open_csv.configure(command=on_open_csv)
    btn_open_dir.configure(command=on_open_dir)
    win.bind("<F5>", lambda e: refresh())
    win.bind("<Return>", lambda e: refresh())

    refresh()
    return win

# nomes-ponte usados pelo main.py
def open_registry_window(parent: tk.Tk | tk.Toplevel):
    return _open_window(parent)

def open_nn_registry(parent: tk.Tk | tk.Toplevel = None):
    return _open_window(parent or tk._default_root)

def open_nn_registry_window(parent: tk.Tk | tk.Toplevel = None):
    return _open_window(parent or tk._default_root)
