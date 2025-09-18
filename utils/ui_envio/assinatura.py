import tkinter as tk
from tkinter import ttk, messagebox, filedialog, colorchooser
from .common import _add_page, html_escape as _html_escape

def html_escape(s: str) -> str:
    return _html_escape(s)

# ---------- util: conversão de TAGs (Text) -> HTML inline ----------
def _text_to_html(txt: tk.Text, family="Segoe UI", size=10) -> str:
    import html
    def tags_at(idx):
        return set(t for t in txt.tag_names(idx) if t in ("bold","italic","underline") or t.startswith("fg#"))

    def color_of(tags):
        for t in tags:
            if t.startswith("fg#"): return t[2:]  # fg#RRGGBB
        return None

    i = "1.0"
    end = txt.index("end-1c")
    cur = set()
    parts = [f'<div style="font-family:{family}; font-size:{size}pt;">']
    while i != end:
        tnow = tags_at(i)
        # fechar tags que saíram
        to_close = cur - tnow
        if to_close:
            # fecha spans de cor primeiro, depois u/i/b
            if any(t.startswith("fg#") for t in to_close): parts.append("</span>")
            if "underline" in to_close: parts.append("</u>")
            if "italic"    in to_close: parts.append("</i>")
            if "bold"      in to_close: parts.append("</b>")
            cur -= to_close
        # abrir tags novas
        to_open = tnow - cur
        if to_open:
            if "bold" in to_open: parts.append("<b>")
            if "italic" in to_open: parts.append("<i>")
            if "underline" in to_open: parts.append("<u>")
            c = color_of(to_open)
            if c: parts.append(f'<span style="color:{c};">')
            cur |= to_open
        ch = txt.get(i)
        if ch == "\n": parts.append("<br>")
        else: parts.append(html.escape(ch))
        i = txt.index(f"{i}+1c")
    # fecha remanescentes
    if any(t.startswith("fg#") for t in cur): parts.append("</span>")
    if "underline" in cur: parts.append("</u>")
    if "italic" in cur: parts.append("</i>")
    if "bold" in cur: parts.append("</b>")
    parts.append("</div>")
    return "".join(parts)

def open_assinatura_tab(container: ttk.Notebook, cfg: dict):
    page = _add_page(container, "Assinatura Padrão")

    # frame "central" dimensionado (3/5 largura, 1/2 altura aparentes)
    inner = tk.Frame(page)
    inner.grid(row=0, column=0, sticky="nw", padx=10, pady=10)

    # toolbar
    tb = ttk.Frame(inner)
    tb.pack(fill="x", padx=8, pady=(8,0))

    # editor
    ed = tk.Text(inner, wrap="word", height=12, font=("Segoe UI", 11))
    ed.pack(fill="both", expand=True, padx=8, pady=(6,8))

    # controles de fonte e cor
    fonts = ["Segoe UI", "Arial", "Calibri", "Times New Roman"]
    v_family = tk.StringVar(value="Segoe UI")
    v_size   = tk.IntVar(value=11)
    ttk.Label(tb, text="Fonte:").pack(side="left")
    cb_font = ttk.Combobox(tb, values=fonts, textvariable=v_family, width=16, state="readonly")
    cb_font.pack(side="left", padx=(4,8))
    ttk.Label(tb, text="Tamanho:").pack(side="left")
    cb_size = ttk.Combobox(tb, values=[9,10,11,12,14,16,18], textvariable=v_size, width=5, state="readonly")
    cb_size.pack(side="left", padx=(4,8))

    def _apply_font(*_):
        ed.configure(font=(v_family.get(), v_size.get()))
    cb_font.bind("<<ComboboxSelected>>", _apply_font)
    cb_size.bind("<<ComboboxSelected>>", _apply_font)

    def _toggle(tag):
        try:
            start, end = ed.index("sel.first"), ed.index("sel.last")
        except Exception:
            return
        if tag.startswith("fg"):
            # remove outras cores
            for t in ed.tag_names():
                if t.startswith("fg#"):
                    ed.tag_remove(t, start, end)
            ed.tag_add(tag, start, end)
            ed.tag_configure(tag, foreground=tag[2:])
            return
        if tag in ed.tag_names("sel.first"):
            ed.tag_remove(tag, start, end)
        else:
            ed.tag_add(tag, start, end)
            if tag == "underline":
                ed.tag_configure("underline", underline=True)
            elif tag == "bold":
                ed.tag_configure("bold", font=(v_family.get(), v_size.get(), "bold"))
            elif tag == "italic":
                ed.tag_configure("italic", font=(v_family.get(), v_size.get(), "italic"))

    ttk.Button(tb, text="N", width=3, command=lambda:_toggle("bold")).pack(side="left")
    ttk.Button(tb, text="I", width=3, command=lambda:_toggle("italic")).pack(side="left", padx=(3,0))
    ttk.Button(tb, text="S", width=3, command=lambda:_toggle("underline")).pack(side="left", padx=(3,8))
    def _pick_color():
        _, hexcolor = colorchooser.askcolor()
        if hexcolor:
            _toggle(f"fg#{hexcolor}")
    ttk.Button(tb, text="Cor…", command=_pick_color).pack(side="left")

    # carrega assinatura existente (HTML -> texto plano simples para exibir)
    raw_html = (cfg.get("smtp_assinatura_texto") or "").strip()
    if raw_html:
        import re, html
        txt = re.sub(r"<br\s*/?>", "\n", raw_html, flags=re.I)
        txt = re.sub(r"<[^>]+>", "", txt)
        ed.insert("1.0", html.unescape(txt))
    else:
        # sugestão inicial
        nome   = cfg.get("smtp_nome_remetente") or cfg.get("razao_social") or ""
        email  = cfg.get("smtp_email") or cfg.get("email") or ""
        fone   = cfg.get("telefone") or ""
        site   = cfg.get("site") or ""
        ed.insert("1.0", f"{nome}\nE-mail: {email}\nTelefone: {fone}\nSite: {site}")

    # seletor de logo + instruções (abaixo do editor)
    bottom_opts = ttk.Frame(inner); bottom_opts.pack(fill="x", padx=8, pady=(0,4))
    v_img = tk.StringVar(value=cfg.get("smtp_assinatura_imagem",""))
    row1 = ttk.Frame(bottom_opts); row1.pack(fill="x")
    ttk.Label(row1, text="Logo do Beneficiário:").pack(side="left")
    entry = ttk.Entry(row1, textvariable=v_img); entry.pack(side="left", fill="x", expand=True, padx=6)
    def _choose_logo():
        path = filedialog.askopenfilename(
            title="Selecione a logo (PNG com fundo transparente de preferência)",
            filetypes=[("Imagens", "*.png;*.jpg;*.jpeg;*.gif;*.bmp"), ("Todos os arquivos","*.*")]
        )
        if not path: return
        v_img.set(path)
    ttk.Button(row1, text="Selecionar logo…", command=_choose_logo).pack(side="left")
    ttk.Label(bottom_opts, text="Sugestão: PNG com fundo transparente, até 400×120 px.").pack(anchor="w", pady=(6,0))

    # ações (somente Salvar e Fechar)
    actions = ttk.Frame(inner); actions.pack(fill="x", padx=8, pady=(6,8))
    def _persist():
        html = _text_to_html(ed, v_family.get(), v_size.get())
        cfg["smtp_assinatura_texto"]  = html
        cfg["smtp_assinatura_imagem"] = v_img.get()
        try:
            from utils.parametros import salvar_parametros
        except Exception:
            from parametros import salvar_parametros
        salvar_parametros(cfg)

    def _fechar():
        try: _persist()
        except Exception: pass
        try: container.forget(page)
        finally:
            try: container.after(0, lambda: container.event_generate("<<NotebookTabChanged>>"))
            except Exception: pass
            if hasattr(container, "_tab_registry"):
                container._tab_registry.pop("Assinatura Padrão", None)

    ttk.Button(actions, text="Fechar", command=_fechar).pack(side="right")
    ttk.Button(actions, text="Salvar", command=_persist).pack(side="right", padx=(0,8))

    # redimensiona o “inner” para 3/5 da largura e 1/2 da altura aparentes
    def _resize(_=None):
        try:
            w = max(600, int(page.winfo_width()*0.6))
            h = max(320, int(page.winfo_height()*0.5))
            inner.configure(width=w, height=h)
        except Exception:
            pass
    page.bind("<Configure>", _resize)
    _resize()
    return page
