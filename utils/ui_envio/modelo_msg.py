# utils/ui_envio/modelo_msg.py
import tkinter as tk
from tkinter import ttk, messagebox

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

def open_modelo_mensagem_tab(container: ttk.Notebook, cfg: dict):
    # registra aba fichário
    title = "Modelo de Mensagem"
    if not hasattr(container, "_tab_registry"): container._tab_registry = {}
    if title in container._tab_registry:
        container.select(container._tab_registry[title]); return container._tab_registry[title]
    page = ttk.Frame(container)
    container.add(page, text=title.ljust(20," "))
    container._tab_registry[title] = page
    container.select(page)

    def _close(*_):
        try: container.forget(page)
        finally:
            try: container.after(0, lambda: container.event_generate("<<NotebookTabChanged>>"))
            except Exception: pass
            container._tab_registry.pop(title, None)
    page._nasapay_close = _close

    page.columnconfigure(0, weight=1); page.rowconfigure(0, weight=1)

    pw = ttk.Panedwindow(page, orient="horizontal"); pw.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

    left = ttk.Frame(pw); left.columnconfigure(0, weight=1); left.rowconfigure(1, weight=1)
    right= ttk.Frame(pw); right.columnconfigure(0, weight=1); right.rowconfigure(1, weight=1)
    pw.add(left, weight=6); pw.add(right, weight=4)

    ttk.Label(left, text="Modelo de Mensagem (padrão)").grid(row=0, column=0, sticky="w")
    txt = tk.Text(left, wrap="word"); txt.grid(row=1, column=0, sticky="nsew", pady=(2,6))
    txt.configure(font=("Segoe UI", 10))
    txt.insert("1.0", (cfg.get("smtp_msg_modelo") or
        "Para: {sacado_razao}\n"
        "Att.: {sacado_contato}\n\n"
        "Ref.: Boletos emitidos por {empresa_razao}\n\n"
        "Caro cliente,\n\n"
        "Seguem, em anexo, boletos referente aos títulos abaixo listados:\n"
        "[[TABELA_TITULOS]]\n\n"
        "Se surgir alguma dúvida, estamos à disposição pelo telefone {empresa_telefone} "
        "ou pelo e-mail {empresa_email}.\n\n"
        "Atenciosamente,"))

    # referências
    ttk.Label(right, text="Selecione entre as referências abaixo para compor a mensagem").grid(row=0, column=0, sticky="w")
    nb = ttk.Notebook(right); nb.grid(row=1, column=0, sticky="nsew", pady=(2,4))

    def _make_tree(parent):
        tv = ttk.Treeview(parent, columns=("desc","ref"), show="headings", selectmode="browse")
        tv.heading("desc", text="Descrição"); tv.heading("ref", text="Referência")
        tv.column("desc", width=230, anchor="w"); tv.column("ref", width=180, anchor="w")
        tv.pack(fill="both", expand=True)
        return tv

    sacado = ttk.Frame(nb); beneficiario = ttk.Frame(nb)
    nb.add(sacado, text="Sacado"); nb.add(beneficiario, text="Beneficiário")
    tvS = _make_tree(sacado); tvB = _make_tree(beneficiario)

    sacado_refs = [
        ("Razão Social", "{sacado_razao}"),
        ("Nome de Contato", "{sacado_contato}"),
        ("Endereço", "{sacado_endereco}"),
        ("Cidade", "{sacado_cidade}"),
        ("UF", "{sacado_uf}"),
        ("CEP", "{sacado_cep}"),
        ("Telefone", "{sacado_telefone}"),
        ("E-mail", "{sacado_email}"),
        ("Nº Documento", "{titulo_doc}"),
        ("Vencimento", "{titulo_venc}"),
        ("Valor", "{titulo_valor}"),
    ]
    beneficiario_refs = [
        ("Razão Social", "{empresa_razao}"),
        ("Endereço", "{empresa_endereco}"),
        ("Cidade", "{empresa_cidade}"),
        ("UF", "{empresa_uf}"),
        ("CEP", "{empresa_cep}"),
        ("Telefone", "{empresa_telefone}"),
        ("E-mail", "{empresa_email}"),
        ("Agência", "{empresa_agencia}"),
        ("Conta", "{empresa_conta}"),
        ("Dígito", "{empresa_digito}"),
    ]
    for d,r in sacado_refs: tvS.insert("", "end", values=(d,r))
    for d,r in beneficiario_refs: tvB.insert("", "end", values=(d,r))

    def _insert_from(tv):
        sel = tv.selection()
        if not sel: return
        ref = tv.item(sel[0], "values")[1]
        try: start = txt.index("insert")
        except tk.TclError: start = "end-1c"
        txt.insert(start, ref)

    tvS.bind("<Double-1>", lambda e: _insert_from(tvS))
    tvB.bind("<Double-1>", lambda e: _insert_from(tvB))

    btnrow = ttk.Frame(right); btnrow.grid(row=2, column=0, sticky="w")
    ttk.Button(btnrow, text="Inserir", command=lambda: _insert_from(tvS if nb.index('current')==0 else tvB)).pack(side="left")

    ttk.Label(left, text="Obs.: Esta assinatura será inserida automaticamente no e-mail ao sacado.")\
        .grid(row=2, column=0, sticky="w")

    actions = ttk.Frame(page); actions.grid(row=1, column=0, sticky="e", padx=10, pady=(0,10))
    def _save():
        cfg["smtp_msg_modelo"] = txt.get("1.0","end").strip()
        try:
            from utils.parametros import salvar_parametros
        except Exception:
            from parametros import salvar_parametros  # fallback
        salvar_parametros(cfg)
        messagebox.showinfo("Modelo de Mensagem", "Modelo salvo.")
        _close()
    def _close(*_):
        try: container.forget(page)
        finally:
            try: container.after(0, lambda: container.event_generate("<<NotebookTabChanged>>"))
            except Exception: pass
            container._tab_registry.pop(title, None)
    ttk.Button(actions, text="Fechar", command=_close).pack(side="right")
    ttk.Button(actions, text="Salvar", command=_save).pack(side="right", padx=(0,8))

    return page
