# utils/ui_envio/core.py
import os, re, tkinter as tk
from tkinter import ttk, messagebox

from utils.parametros import carregar_parametros
from utils.ui_busy import run_with_busy

from .assinatura import open_assinatura_tab, html_escape
from .smtp import send_html, img_to_cid
from . import data as ds
from .pdftext import extract_text  # retorna texto ou ""

# ---------------- util notebook / abas ----------------
def _add_page(container, titulo_base: str):
    titulo = (titulo_base[:20] if len(titulo_base) > 20 else titulo_base.ljust(20, " "))
    if not hasattr(container, "_tab_registry"):
        container._tab_registry = {}
    if titulo_base in container._tab_registry:
        container.select(container._tab_registry[titulo_base])
        return container._tab_registry[titulo_base]
    page = ttk.Frame(container)
    container.add(page, text=titulo)
    container._tab_registry[titulo_base] = page
    container.select(page)

    def _close(direct=False, **_):
        try:
            container.forget(page)
        finally:
            try:
                container.after(0, lambda: container.event_generate("<<NotebookTabChanged>>"))
            except Exception:
                pass
            container._tab_registry.pop(titulo_base, None)

    page._nasapay_close = _close
    return page

# ------------- helpers de UI (centralizar popups) -------------
def _center_on_parent(top: tk.Toplevel, parent):
    try:
        top.update_idletasks()
        if parent is None:
            parent = top.winfo_toplevel()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        tw = top.winfo_width()
        th = top.winfo_height()
        x = px + (pw - tw)//2
        y = py + (ph - th)//2
        top.geometry(f"+{max(0,x)}+{max(0,y)}")
        top.transient(parent)
        top.grab_set()
        top.focus_force()
    except Exception:
        try:
            top.grab_set()
        except Exception:
            pass

# ------------------- HTML do e-mail -------------------
def _titles_table_html(titles):
    if not titles:
        return "<i>Nenhum título selecionado.</i>"
    rows = ['<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-size:10pt;">',
            "<tr><th>Nº Documento</th><th>Vencimento</th><th>Valor</th></tr>"]
    for t in titles:
        rows.append(
            f"<tr><td>{html_escape(str(t.get('doc','')))}</td>"
            f"<td>{html_escape(str(t.get('venc','')))}</td>"
            f"<td>{html_escape(str(t.get('valor','')))}</td></tr>"
        )
    rows.append("</table>")
    return "\n".join(rows)

def _build_html_message(cfg, raw_msg, pagador, titles_for_send):
    token = "__TITULOS__"
    body = (raw_msg or "")

    # substituições básicas
    body = body.replace("{sacado_razao}",   pagador.get("razao", ""))
    body = body.replace("{sacado_contato}", pagador.get("contato", ""))
    body = body.replace("{empresa_razao}",  cfg.get("razao_social", ""))
    body = body.replace("{empresa_telefone}", cfg.get("telefone", ""))
    body = body.replace("{empresa_email}",    cfg.get("email", ""))
    body = body.replace("[[TABELA_TITULOS]]", token)

    esc = html_escape(body).replace("\n", "<br>")
    lines = esc.split("<br>")

    def fmt_line_prefix(line, prefix, open_tag, close_tag):
        if line.startswith(prefix):
            content = line[len(prefix):].strip()
            return f"{prefix}{open_tag}{content}{close_tag}"
        return line

    lines = [fmt_line_prefix(ln, "Para: ", "<b>", "</b>") for ln in lines]
    lines = [fmt_line_prefix(ln, "Att.: ", "<u>", "</u>") for ln in lines]

    def fmt_ref(line):
        pref = "Ref.: Boletos emitidos por "
        if line.startswith(pref):
            name = line[len(pref):].strip()
            return f"{pref}<b>{name}</b>"
        return line

    lines = [fmt_ref(ln) for ln in lines]

    body_html = "<br>".join(lines).replace(token, _titles_table_html(titles_for_send))
    html = f'<div style="font-family:Segoe UI, Arial, sans-serif; font-size:10pt;">{body_html}</div>'

    inline = []
    assinatura = (cfg.get("smtp_assinatura_texto", "") or "").strip()
    img_path = (cfg.get("smtp_assinatura_imagem", "") or "").strip()
    if assinatura:
        html += "<br>" + assinatura
    if img_path and os.path.exists(img_path):
        cid, ctype, data = img_to_cid(img_path)
        inline.append(("inline", cid, ctype, data))
        html += f'<br><img src="cid:{cid}">'
    return html, inline

# ---------------- seleção atual / anexos ----------------
def _current_pagador(page):
    tvP = page._tvP
    sel = tvP.selection()
    if not sel:
        return None, None
    iid = sel[0]
    vals = tvP.item(iid, "values")
    return iid, {"id": iid, "razao": vals[0], "fantasia": vals[1],
                 "fone": vals[2], "email": vals[3], "contato": vals[4]}

def _selected_titles(page):
    """
    Retorna [(pid, registro_titulo_dict), ...].
    Se nada estiver marcado, abre o popup e, em caso de confirmação ("Sim"),
    já MARCA os títulos conforme a escolha **e retorna a seleção** (para enviar).
    """
    tvT = page._tvT
    if page._sel_titles:
        out = []
        for iid in list(page._sel_titles):
            pid, doc = iid.split("|", 1)
            t = next((x for x in page._map_titles.get(pid, []) if str(x.get("doc")) == doc), None)
            if t:
                out.append((pid, t))
        return out

    pid, _ = _current_pagador(page)
    if pid:
        # popup customizado (3 botões)
        top = tk.Toplevel(tvT)
        top.title("Seleção de títulos")
        ttk.Label(
            top,
            text="Ops... vi que você não selecionou nenhum título.\nDeseja enviar todos os títulos deste sacado?"
        ).pack(padx=14, pady=(14, 10))
        btns = ttk.Frame(top)
        btns.pack(pady=(0, 14))
        resp = {"val": "choose"}

        def _only_not():
            resp["val"] = "only_not"; top.destroy()

        def _all():
            resp["val"] = "all";      top.destroy()

        def _choose():
            resp["val"] = "choose";   top.destroy()

        ttk.Button(btns, text="Sim. Apenas com status 'não enviados'", command=_only_not).pack(side="left", padx=6)
        ttk.Button(btns, text="Sim. Todos", command=_all).pack(side="left", padx=6)
        ttk.Button(btns, text="Não. Escolher títulos", command=_choose).pack(side="left", padx=6)
        _center_on_parent(top, tvT.winfo_toplevel())
        top.wait_window()

        # Se o usuário escolheu uma das opções "Sim", marcamos e devolvemos a seleção
        if resp["val"] in ("all", "only_not"):
            page._sel_titles.clear()
            for child in tvT.get_children():
                st = (tvT.set(child, "status") or "").strip().lower()
                if resp["val"] == "all" or st.startswith("não enviado"):
                    page._sel_titles.add(child)
                    tvT.set(child, "sel", "☑")
            # já devolve a lista marcada, para seguir com o envio
            out = []
            for iid in list(page._sel_titles):
                pid2, doc2 = iid.split("|", 1)
                t = next((x for x in page._map_titles.get(pid2, []) if str(x.get("doc")) == doc2), None)
                if t:
                    out.append((pid2, t))
            return out

        # "Não" => deixa o usuário escolher, sem enviar agora
        return []
    return []

def _collect_attachments(cfg, choice, page=None):
    # Mantido (futuro). Não é usado nos botões, conforme solicitação.
    files = []
    for pid, t in choice:
        pdfs = list(t.get("pdfs") or [])
        if not pdfs:
            alt = _find_pdf_for_title(cfg, t, page=page)
            if alt:
                pdfs = [alt]
        extras = list(t.get("extras") or [])
        files += [p for p in (pdfs + extras) if p and os.path.exists(p)]
    return files

# --------- (internos para automatch; mantidos, mas não exibimos botões) ---------
def _candidate_pdf_dirs(cfg, page):
    base = []
    if getattr(page, "_last_pdf_dir", None):
        base.append(page._last_pdf_dir)
    for k in ("pasta_saida", "pasta_entrada"):
        p = (cfg.get(k) or "").strip()
        if p and os.path.isdir(p):
            base.append(p)
    for p in (r"C:\nasapay\boletos", r"C:\nasapay\arquivos", r"C:\nasapay\remessas", r"C:\nasapay"):
        if os.path.isdir(p):
            base.append(p)
    seen = set()
    out = []
    for p in base:
        if p not in seen:
            out.append(p)
            seen.add(p)
    return out

def _find_pdf_for_title(cfg, t, page=None):
    keys = []
    if t.get("doc"):
        keys.append(re.sub(r"\D", "", str(t["doc"])))
    if t.get("nosso"):
        keys.append(re.sub(r"\D", "", str(t["nosso"])))
    keys = [k for k in keys if k]
    if not keys:
        return None
    for folder in _candidate_pdf_dirs(cfg, page):
        try:
            for fn in os.listdir(folder):
                if not fn.lower().endswith(".pdf"):
                    continue
                digits = re.sub(r"\D", "", fn)
                if any(k and k in digits for k in keys):
                    return os.path.join(folder, fn)
        except Exception:
            continue
    return None

# ------------------- envio -------------------
def _enviar_sacados(page, cfg, subject, raw_msg):
    pid, pag = _current_pagador(page)
    if not pid:
        messagebox.showwarning("Envio", "Selecione um sacado.", parent=page)
        return
    if not (pag.get("email") or "").strip():
        messagebox.showwarning(
            "Envio",
            "Informe o e-mail do sacado (duplo clique na coluna E-MAIL para editar).",
            parent=page,
        )
        return

    choice = _selected_titles(page)
    if not choice:
        return
    titles = [t for _pid, t in choice]
    if not titles:
        messagebox.showwarning("Envio", "Nenhum título selecionado.", parent=page)
        return

    already = [t for t in titles if (t.get("send_count") or 0) >= 1 or (t.get("first_ts") or t.get("last_ts"))]
    subj = subject
    if already:
        first_dates = [t.get("first_ts") or t.get("last_ts") for t in already if (t.get("first_ts") or t.get("last_ts"))]
        show_dt = ""
        if first_dates:
            try:
                show_dt = ds._fmt_br_dt(sorted(first_dates)[0])
            except Exception:
                show_dt = first_dates[0]
        top = tk.Toplevel(page)
        top.title("Reenvio")
        ttk.Label(top, text=f"Título já foi enviado em {show_dt}.\nDeseja enviar novamente?").pack(padx=16, pady=(16, 10))
        btns = ttk.Frame(top); btns.pack(pady=(0, 12))
        resp = {"ok": False}
        ttk.Button(btns, text="Sim", command=lambda: (resp.update(ok=True), top.destroy())).pack(side="left", padx=6)
        ttk.Button(btns, text="Não", command=top.destroy).pack(side="left", padx=6)
        _center_on_parent(top, page.winfo_toplevel()); top.wait_window()
        if not resp["ok"]:
            return
        subj = f"Envio de 2ª via de boleto - {cfg.get('razao_social', '')}"

    # Não exibimos botões de anexos; segue tentativa de localizar automaticamente
    files = _collect_attachments(cfg, choice, page=page)

    html, inline = _build_html_message(cfg, raw_msg, pag, titles)

    def work():
        send_html(cfg, pag["email"], subj, html, inline, files)
        now_iso = ds.record_send(page, [t.get("tid") for t in titles if t.get("tid") is not None])
        for _pid, t in choice:
            t["send_count"] = int(t.get("send_count") or 0) + 1
            t["last_ts"] = now_iso
            t["first_ts"] = t.get("first_ts") or now_iso
        return pag["email"], len(titles), [f"{_pid}|{t.get('doc','')}" for _pid, t in choice], now_iso

    def done(res, err):
        if err:
            messagebox.showerror("Envio", f"Falha no envio: {err}", parent=page)
            return
        email, qtd, iids, now_iso = res
        from . import data as _ds
        now_txt = _ds._fmt_br_dt(now_iso)
        messagebox.showinfo("Envio", f"{qtd} título(s) enviados para {email}", parent=page)
        for iid in iids:
            try:
                pid, doc = iid.split("|", 1)
                t = next((x for x in page._map_titles.get(pid, []) if str(x.get("doc")) == doc), None)
                if not t:
                    continue
                label = "enviado em " + now_txt if t.get("send_count") == 1 else "reenviado em " + now_txt
                page._tvT.set(iid, "status", label)
                page._tvT.set(iid, "sel", "☐")
                if iid in page._sel_titles:
                    page._sel_titles.remove(iid)
            except Exception:
                pass

    run_with_busy(page, "Enviando boletos…", work, done)

# ------------------- UI principal (Envio p/ Sacado) -------------------

def _ui_envio_sacado(container, cfg):
    page = _add_page(container, "Selecionar Títulos")
    page.columnconfigure(0, weight=1)
    # 0 = listas (topo), 1 = mensagem, 2 = ações/rodapé
    page.rowconfigure(0, weight=1)
    page.rowconfigure(1, weight=2)
    page.rowconfigure(2, minsize=72)   # botões visíveis

    import unicodedata, re
    def _norm(s: str) -> str:
        s = (s or "").lower()
        s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
        return s
    def _digits(s: str) -> str:
        return re.sub(r"\D", "", s or "")

    # ---------------- Painel central (Sacados x Títulos) ----------------
    main = ttk.Panedwindow(page, orient="horizontal")
    main.grid(row=0, column=0, sticky="nsew", padx=10, pady=(10, 6))
    left = ttk.Frame(main);  left.columnconfigure(0, weight=1);  left.rowconfigure(3, weight=1)
    right = ttk.Frame(main); right.columnconfigure(0, weight=1); right.rowconfigure(3, weight=1)
    main.add(left,  weight=4)
    main.add(right, weight=6)

    # ---------------- Sacados (filtro + limpar) ----------------
    ttk.Label(left, text="Sacados").grid(row=0, column=0, sticky="w")
    hL = ttk.Frame(left); hL.grid(row=1, column=0, sticky="ew"); hL.columnconfigure(0, weight=1)
    ttk.Label(hL, text="Pesquise por nome de Sacado").grid(row=0, column=0, sticky="w")
    v_busca_p = tk.StringVar()
    ent_busca_p = ttk.Entry(left, textvariable=v_busca_p); ent_busca_p.grid(row=2, column=0, sticky="ew", pady=(0,2))
    btn_clear_sel = ttk.Button(hL, text="Limpar Pesquisa (ESC)", width=20); btn_clear_sel.grid(row=0, column=1, sticky="e")

    colsP = ("razao","fantasia","fone","email","contato")
    tvP = ttk.Treeview(left, columns=colsP, show="headings", selectmode="browse", height=10)
    for c,h,w in zip(colsP, ("RAZÃO SOCIAL","NOME FANTASIA","TELEFONE","E-MAIL","NOME DE CONTATO"),
                     (220,180,120,220,160)):
        tvP.heading(c, text=h); tvP.column(c, width=w, anchor="w")
    tvP.grid(row=3, column=0, sticky="nsew", pady=(4,0))

    def _clear_sel(*_):
        try: tvP.selection_remove(tvP.selection())
        except Exception: pass
        ds.refresh_pagadores(page, v_busca_p.get()); _refresh_titles()
    btn_clear_sel.configure(command=_clear_sel)
    tvP.bind("<Escape>", lambda e: _clear_sel())
    ent_busca_p.bind("<Escape>", lambda e: v_busca_p.set(""))

    # edição inline básica
    def _commit_edit(item, col, value):
        if col == "fone": value = ds._fmt_email(value) if "@" in value else ds._fmt_phone(value)
        if col == "email": value = ds._fmt_email(value)
        if col in ("fantasia","contato"): value = (value or "").upper().strip()
        if col == "email" and value and not ds._is_valid_email(value):
            messagebox.showwarning("E-mail", "E-mail inválido.", parent=page); return
        tvP.set(item, col, value)
        row = next((p for p in page._map_pags if p["id"] == item), None)
        if row: row[col] = value
        try: ds.save_pagador_field(page, item, col, value)
        except Exception as e: messagebox.showerror("Salvar", f"Falha ao salvar: {e}", parent=page)

    def _start_edit(event):
        item = tvP.identify_row(event.y); col = tvP.identify_column(event.x)
        if not item or col == "#1": return
        colname = {"#2":"fantasia","#3":"fone","#4":"email","#5":"contato"}.get(col)
        if not colname: return
        x,y,w,h = tvP.bbox(item, col)
        editor = ttk.Entry(tvP); editor.insert(0, tvP.set(item, colname))
        editor.select_range(0,"end"); editor.focus_set()
        editor.place(x=x, y=y, width=w, height=h)
        editor.bind("<Return>", lambda e,i=item,c=colname: (_commit_edit(i,c,editor.get()), editor.destroy()))
        editor.bind("<Escape>", lambda e: editor.destroy())
    tvP.bind("<Double-1>", _start_edit)

    # ---------------- Títulos (filtro + limpar + checkbox) ----------------
    ttk.Label(right, text="Títulos").grid(row=0, column=0, sticky="w")
    hR = ttk.Frame(right); hR.grid(row=1, column=0, sticky="ew"); hR.columnconfigure(0, weight=1)
    ttk.Label(hR, text="Pesquise por Nº Docto, Vencimento ou Valor").grid(row=0, column=0, sticky="w")
    v_ft = tk.StringVar()
    ent_ft = ttk.Entry(right, textvariable=v_ft); ent_ft.grid(row=2, column=0, sticky="ew")
    def _clear_ft():
        v_ft.set("")
        ent_ft.focus_set()
        _refresh_titles()
    ttk.Button(hR, text="Limpar Pesquisa (ESC)", command=_clear_ft).grid(row=0, column=1, sticky="e")
    ent_ft.bind("<Escape>", lambda e: _clear_ft())

    # coluna 0 = checkbox; depois: Nº DOCTO, VCTO, VALOR, NOSSO NÚMERO, STATUS
    colsT = ("sel","doc","venc","valor","nosso","status")
    tvT = ttk.Treeview(right, columns=colsT, show="headings", selectmode="browse", height=10)
    headers = {
        "sel":   ("",         34,  "center"),
        "doc":   ("Nº DOCTO", 110, "w"),
        "venc":  ("VCTO",     100, "w"),
        "valor": ("VALOR",    120, "e"),
        "nosso": ("NOSSO NÚMERO", 130, "w"),
        "status":("STATUS E-MAIL", 150, "w"),
    }
    for c in colsT:
        h, w, anch = headers[c][0], headers[c][1], headers[c][2]
        tvT.heading(c, text=h); tvT.column(c, width=w, anchor=anch, stretch=False)
    tvT.grid(row=3, column=0, sticky="nsew", pady=(4,0))

    # "checkbox" via símbolos unicode
    CHECK_OFF = "☐"
    CHECK_ON  = "☑"

    page._tvP = tvP; page._tvT = tvT
    page._map_pags = []; page._map_titles = {}; page._sel_titles = set(); page._last_pdf_dir = None

    def _match_title(q: str, t: dict) -> bool:
        if not q: return True
        doc = str(t.get("doc","")); venc = str(t.get("venc","")); valor = str(t.get("valor",""))
        if q.isdigit():
            qd = q
            return (qd in _digits(doc)) or (qd in _digits(venc)) or (qd in _digits(valor))
        qn = _norm(q)
        return (qn in _norm(doc)) or (qn in _norm(venc)) or (qn in _norm(valor))

    def _refresh_titles(*_):
        q = (v_ft.get() or "").strip()
        tvT.delete(*tvT.get_children())
        sel = tvP.selection()

        def add_row(pid, t):
            iid = f"{pid}|{t.get('doc','')}"
            tvT.insert("", "end", iid=iid, values=(
                CHECK_ON if iid in page._sel_titles else CHECK_OFF,
                t.get("doc",""),
                t.get("venc",""),
                t.get("valor",""),
                t.get("nosso",""),
                t.get("status","não enviado"),
            ))

        if sel:
            pid = sel[0]
            for t in page._map_titles.get(pid, []):
                if _match_title(q, t): add_row(pid, t)
        else:
            for pid, items in page._map_titles.items():
                for t in items:
                    if _match_title(q, t): add_row(pid, t)

    v_ft.trace_add("write", _refresh_titles)
    tvP.bind("<<TreeviewSelect>>", _refresh_titles)
    v_busca_p.trace_add("write", lambda *_: ds.refresh_pagadores(page, v_busca_p.get()))

    def _toggle_checkbox(iid):
        if iid in page._sel_titles: page._sel_titles.remove(iid)
        else: page._sel_titles.add(iid)
        tvT.set(iid, "sel", CHECK_ON if iid in page._sel_titles else CHECK_OFF)

    def on_click_titles(event):
        item = tvT.identify_row(event.y); col = tvT.identify_column(event.x)
        if not item: return
        if col == "#1":  # coluna checkbox
            _toggle_checkbox(item)
        else:
            pid = item.split("|",1)[0]
            try: tvP.selection_set(pid); tvP.see(pid)
            except Exception: pass
            _refresh_titles()
    tvT.bind("<Button-1>", on_click_titles)
    tvT.bind("<space>", lambda e: (_toggle_checkbox(tvT.selection()[0]) if tvT.selection() else None))

    # ---------------- Mensagem e Assunto (auto-salvar) ----------------
    msgframe = ttk.Frame(page); msgframe.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0,6))
    msgframe.columnconfigure(0, weight=1); msgframe.rowconfigure(2, weight=1)
    ttk.Label(msgframe, text="Mensagem ao Sacado").grid(row=0, column=0, sticky="w")

    subj_row = ttk.Frame(msgframe); subj_row.grid(row=1, column=0, sticky="ew", pady=(2,4))
    ttk.Label(subj_row, text="Assunto:", width=10, anchor="e").pack(side="left")
    subj_v = tk.StringVar(value=cfg.get("smtp_assunto_padrao") or f"Boleto - {cfg.get('razao_social','')}")
    ent_subj = ttk.Entry(subj_row, textvariable=subj_v, width=60); ent_subj.pack(side="left", padx=(6,0))

    _save_job = {"id": None}
    def _persist_subject():
        cfg["smtp_assunto_padrao"] = subj_v.get().strip()
        try:
            from utils.parametros import salvar_parametros
        except Exception:
            from parametros import salvar_parametros
        try: salvar_parametros(cfg)
        except Exception: pass
    def _on_subj_change(*_):
        if _save_job["id"] is not None:
            try: page.after_cancel(_save_job["id"])
            except Exception: pass
        _save_job["id"] = page.after(800, _persist_subject)
    subj_v.trace_add("write", _on_subj_change)

    txt_msg = tk.Text(msgframe, wrap="word", height=10); txt_msg.configure(font=("Segoe UI",10))
    txt_msg.grid(row=2, column=0, sticky="nsew")
    modelo_default = (
        "Para: {sacado_razao}\n"
        "Att.: {sacado_contato}\n\n"
        f"Ref.: Boletos emitidos por {cfg.get('razao_social','')}\n\n"
        "Caro cliente,\n\n"
        "Seguem, em anexo, boletos referente aos títulos abaixo listados:\n"
        "[[TABELA_TITULOS]]\n\n"
        "Se surgir alguma dúvida, estamos à disposição pelo telefone {empresa_telefone} "
        "ou pelo e-mail {empresa_email}.\n\n"
        "Atenciosamente,"
    )
    txt_msg.insert("1.0", cfg.get("smtp_msg_modelo") or modelo_default)

    # ---------------- Rodapé ----------------
    actions = ttk.Frame(page); actions.grid(row=2, column=0, sticky="ew", padx=10, pady=(0,10))
    actions.columnconfigure(0, weight=1)
    ttk.Button(actions, text="Editar Mensagem", command=lambda: open_modelo_tab(container, cfg)).pack(side="left")
    ttk.Button(actions, text="Enviar",
               command=lambda: _enviar_sacados(page, cfg, subj_v.get(), txt_msg.get("1.0","end"))).pack(side="left", padx=(8,0))
    ttk.Button(actions, text="Fechar", command=lambda: page._nasapay_close(True)).pack(side="left", padx=(8,0))

    # ---------------- ESC global na ABA ----------------
    def _on_escape(_=None):
        q = (v_ft.get() or "")
        if q.strip():
            _clear_ft(); return
        # se não há texto para limpar, limpa seleção de títulos; senão sacados
        if tvT.selection():
            page._sel_titles.clear(); _refresh_titles(); return
        _clear_sel()
    # liga ESC para tudo da aba e desliga ao destruir
    page.bind_all("<Escape>", _on_escape)
    page.bind("<Destroy>", lambda e: page.unbind_all("<Escape>"))

    # ---------------- Carga inicial ----------------
    try:
        ds.load_initial(page)
        ds.refresh_pagadores(page, v_busca_p.get())
        _refresh_titles()
    except Exception as e:
        messagebox.showwarning("Fonte de dados", f"Não consegui ler o banco padrão.\nDetalhe: {e}", parent=page)



# ------------------- Modelo de Mensagem -------------------

def open_modelo_tab(container: ttk.Notebook, cfg: dict):
    page = _add_page(container, "Modelo de Mensagem")
    page.columnconfigure(0, weight=3)   # esquerda = editor
    page.columnconfigure(1, weight=2)   # direita = referências
    page.rowconfigure(0, weight=1)

    # --------- Editor visual ----------
    left = ttk.Frame(page); left.grid(row=0, column=0, sticky="nsew", padx=(10,6), pady=10)
    left.columnconfigure(0, weight=1); left.rowconfigure(1, weight=1)

    tb = ttk.Frame(left); tb.grid(row=0, column=0, sticky="ew")
    ed = tk.Text(left, wrap="word", height=18, font=("Segoe UI", 11))
    ed.grid(row=1, column=0, sticky="nsew", pady=(6,6))

    fonts = ["Segoe UI","Arial","Calibri","Times New Roman"]
    v_family = tk.StringVar(value="Segoe UI"); v_size = tk.IntVar(value=11)
    ttk.Label(tb, text="Fonte:").pack(side="left")
    cb_f = ttk.Combobox(tb, values=fonts, textvariable=v_family, width=16, state="readonly"); cb_f.pack(side="left", padx=(4,8))
    ttk.Label(tb, text="Tam.:").pack(side="left")
    cb_s = ttk.Combobox(tb, values=[9,10,11,12,14,16,18], textvariable=v_size, width=5, state="readonly"); cb_s.pack(side="left", padx=(4,8))
    def _apply_font(*_): ed.configure(font=(v_family.get(), v_size.get()))
    cb_f.bind("<<ComboboxSelected>>", _apply_font); cb_s.bind("<<ComboboxSelected>>", _apply_font)

    def _toggle(tag):
        try: s, e = ed.index("sel.first"), ed.index("sel.last")
        except Exception: return
        if tag in ed.tag_names("sel.first"):
            ed.tag_remove(tag, s, e)
        else:
            ed.tag_add(tag, s, e)
            if tag == "underline": ed.tag_configure("underline", underline=True)
            elif tag == "bold":    ed.tag_configure("bold", font=(v_family.get(), v_size.get(), "bold"))
            elif tag == "italic":  ed.tag_configure("italic", font=(v_family.get(), v_size.get(), "italic"))
    ttk.Button(tb, text="N", width=3, command=lambda:_toggle("bold")).pack(side="left")
    ttk.Button(tb, text="I", width=3, command=lambda:_toggle("italic")).pack(side="left", padx=(3,0))
    ttk.Button(tb, text="S", width=3, command=lambda:_toggle("underline")).pack(side="left", padx=(3,8))

    # carrega texto atual (mantém TEXTO para compatibilidade)
    modelo_default = (
        "Para: {sacado_razao}\n"
        "Att.: {sacado_contato}\n\n"
        f"Ref.: Boletos emitidos por {cfg.get('razao_social','')}\n\n"
        "Caro cliente,\n\n"
        "Seguem, em anexo, boletos referente aos títulos abaixo listados:\n"
        "[[TABELA_TITULOS]]\n\n"
        "Se surgir alguma dúvida, estamos à disposição pelo telefone {empresa_telefone} "
        "ou pelo e-mail {empresa_email}.\n\n"
        "Atenciosamente,"
    )
    ed.insert("1.0", cfg.get("smtp_msg_modelo") or modelo_default)

    # --------- Referências (lado direito) ----------
    right = ttk.Frame(page); right.grid(row=0, column=1, sticky="nsew", padx=(6,10), pady=10)
    right.columnconfigure(0, weight=1); right.rowconfigure(1, weight=1)
    ttk.Label(right, text="Insira referências com duplo clique").grid(row=0, column=0, sticky="w")
    nb = ttk.Notebook(right); nb.grid(row=1, column=0, sticky="nsew", pady=(2,4))

    def _make_tree(parent):
        tv = ttk.Treeview(parent, columns=("desc","ref"), show="headings", selectmode="browse", height=14)
        tv.heading("desc", text="Descrição"); tv.heading("ref", text="Referência")
        tv.column("desc", width=220, anchor="w"); tv.column("ref", width=180, anchor="w")
        tv.pack(fill="both", expand=True)
        return tv

    sacado = ttk.Frame(nb); beneficiario = ttk.Frame(nb)
    nb.add(sacado, text="Sacado"); nb.add(beneficiario, text="Beneficiário")
    tvS = _make_tree(sacado); tvB = _make_tree(beneficiario)

    sacado_refs = [
        ("Razão Social", "{sacado_razao}"), ("Nome de Contato", "{sacado_contato}"),
        ("Endereço", "{sacado_endereco}"), ("Cidade", "{sacado_cidade}"),
        ("UF", "{sacado_uf}"), ("CEP", "{sacado_cep}"), ("Telefone", "{sacado_telefone}"),
        ("E-mail", "{sacado_email}"), ("Nº Documento", "{titulo_doc}"),
        ("Vencimento", "{titulo_venc}"), ("Valor", "{titulo_valor}"),
    ]
    beneficiario_refs = [
        ("Razão Social", "{empresa_razao}"), ("Endereço", "{empresa_endereco}"),
        ("Cidade", "{empresa_cidade}"), ("UF", "{empresa_uf}"),
        ("CEP", "{empresa_cep}"), ("Telefone", "{empresa_telefone}"),
        ("E-mail", "{empresa_email}"), ("Agência", "{empresa_agencia}"),
        ("Conta", "{empresa_conta}"), ("Dígito", "{empresa_digito}"),
    ]
    for d,r in sacado_refs: tvS.insert("", "end", values=(d,r))
    for d,r in beneficiario_refs: tvB.insert("", "end", values=(d,r))

    def _insert_from(tv):
        sel = tv.selection()
        if not sel: return
        ref = tv.item(sel[0], "values")[1]
        try: start = ed.index("insert")
        except tk.TclError: start = "end-1c"
        ed.insert(start, ref)
    tvS.bind("<Double-1>", lambda e: _insert_from(tvS))
    tvB.bind("<Double-1>", lambda e: _insert_from(tvB))

    # --------- Ações (abaixo do editor, à esquerda) ----------
    actions = ttk.Frame(left); actions.grid(row=2, column=0, sticky="e", pady=(0,0))
    def _fechar():
        try: container.forget(page)
        finally:
            try: container.event_generate("<<NotebookTabChanged>>")
            except Exception: pass
            if hasattr(container, "_tab_registry"):
                container._tab_registry.pop("Modelo de Mensagem", None)
    def _salvar():
        cfg["smtp_msg_modelo"] = ed.get("1.0","end").strip()
        try:
            from utils.parametros import salvar_parametros
        except Exception:
            from parametros import salvar_parametros
        salvar_parametros(cfg)
        messagebox.showinfo("Modelo de Mensagem", "Modelo salvo.")
        _fechar()
    ttk.Button(actions, text="Fechar", command=_fechar).pack(side="right")
    ttk.Button(actions, text="Salvar", command=_salvar).pack(side="right", padx=(0,8))



# --------------- API pública ---------------
def open_envio_boletos(parent=None, container: ttk.Notebook | None = None, modo: str = "sacado"):
    if container is None:
        win = tk.Toplevel(parent)
        win.title("Envio de Boletos")
        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)
        container = nb
    cfg = carregar_parametros()
    if modo == "nasa":
        return _add_page(container, "Envio para Nasa")
    elif modo == "assinatura":
        return open_assinatura_tab(container, cfg)
    elif modo == "modelo":
        return open_modelo_tab(container, cfg)
    else:
        return _ui_envio_sacado(container, cfg)
