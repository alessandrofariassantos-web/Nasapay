# main.py — Nasapay • Remessa e Retorno • v2.0 (versão consolidada)
from utils import store, session
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os, sys, traceback, importlib, types
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageFont

VERSAO = "2.0"

# ===================== PATHS =====================
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UTILS_DIR = os.path.join(BASE_DIR, "utils")
SRC_DIR   = os.path.join(BASE_DIR, "src")

for p in (BASE_DIR, UTILS_DIR, SRC_DIR):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

# Alias para utils.cadastros -> cadastros (opcional)
try:
    _cad_pkg = importlib.import_module("utils.cadastros")
    sys.modules.setdefault("cadastros", _cad_pkg)
except Exception:
    pass

# ===================== LOG/EXCEPT =================
LOG_PATH = os.path.join(BASE_DIR, "startup_log.txt")
def _excepthook(exc_type, exc, tb):
    msg = "".join(traceback.format_exception(exc_type, exc, tb))
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write("\n" + "="*70 + "\n" + msg)
    except Exception:
        pass
    try:
        messagebox.showerror("Erro inesperado", msg[:4000])
    except Exception:
        print(msg, file=sys.stderr)
sys.excepthook = _excepthook

# ===================== VISUAL =====================
MAIN_BG = "#ffffff"
TOP_BG  = "#f0f0f0"

def _preferred_logo_path():
    for p in (
        r"C:\nasapay\logo_nasapay.png",
        r"C:\nasapay\Logo Nasapay.png",
        r"C:\nasapay\Logo_nasapay.png",
    ):
        if os.path.exists(p):
            return p
    return None

def _kill_near_white(img_rgba, thr=248):
    if img_rgba.mode != "RGBA":
        img_rgba = img_rgba.convert("RGBA")
    px = img_rgba.load()
    w, h = img_rgba.size
    for y in range(h):
        for x in range(w):
            r,g,b,a = px[x,y]
            if a > 0 and r >= thr and g >= thr and b >= thr:
                px[x,y] = (r,g,b,0)
    return img_rgba

def _fallback_logo():
    W,H = 1200, 400
    img = Image.new("RGBA", (W,H), (255,255,255,0))
    d = ImageDraw.Draw(img)
    text = "nasapay"
    try:
        font = ImageFont.truetype("segoeui.ttf", 160)
    except Exception:
        font = ImageFont.load_default()
    tw, th = d.textsize(text, font=font)
    d.text(((W-tw)//2, (H-th)//2), text, font=font, fill=(0,0,0,50))
    return img

def _fmt_cnpj_mask(cnpj: str | None) -> str:
    d = "".join(ch for ch in (cnpj or "") if ch.isdigit())
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}" if len(d) == 14 else (cnpj or "")

# ===================== MENU LABEL =================
class MenuLabel(tk.Frame):
    def __init__(self, master, text, dropdown=None):
        super().__init__(master, bg=master["bg"])
        self.dropdown = dropdown
        self.f_normal = tkfont.Font(family="Segoe UI", size=10, weight="normal")
        self.f_bold   = tkfont.Font(family="Segoe UI", size=10, weight="bold")
        self.lbl = tk.Label(self, text=text, bg=master["bg"], font=self.f_normal)
        self.lbl.pack(padx=12, pady=(7, 3))
        self.underline = tk.Frame(self, bg="#bdbdbd", height=2)
        self.underline.place_forget()
        for w in (self, self.lbl):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)
    def _on_enter(self,_=None):
        self.lbl.configure(font=self.f_bold)
        self.underline.place(relx=0, rely=1.0, relwidth=1.0, y=-2)
    def _on_leave(self,_=None):
        self.lbl.configure(font=self.f_normal)
        self.underline.place_forget()
    def _on_click(self,_=None):
        if callable(self.dropdown):
            m = self.dropdown()
        else:
            m = None
        if m is None:
            # dropdown pode ser um Menu pronto
            m = self.dropdown if isinstance(self.dropdown, tk.Menu) else None
        if m:
            x = self.winfo_rootx()
            y = self.winfo_rooty() + self.winfo_height()
            try:
                m.tk_popup(x, y)
            finally:
                m.grab_release()

# ============== RESOLVERS AUX (módulos opcionais) ==============
def _resolve_open_envio_boletos():
    """Retorna (fn, err). fn = open_envio_boletos(parent, container, modo)"""
    last_err = None
    for modname in ("utils.ui_envio", "utils.ui_envio.core"):
        try:
            mod = importlib.import_module(modname)
            if hasattr(mod, "open_envio_boletos"):
                return getattr(mod, "open_envio_boletos"), None
        except Exception as e:
            last_err = str(e)
    return None, (last_err or "módulo não encontrado")

def _resolve_nn_registry():
    try:
        from utils.nn_registry_ui import open_nn_registry
        return open_nn_registry, None
    except Exception as e:
        return None, str(e)

# ======== FALLBACK p/ cadastros ausentes ========
def _ensure_cadastros_pkg():
    if "cadastros" not in sys.modules:
        try:
            _pkg = importlib.import_module("utils.cadastros")
            sys.modules["cadastros"] = _pkg
        except Exception:
            pkg = types.ModuleType("cadastros"); pkg.__path__ = []
            sys.modules["cadastros"] = pkg

def _install_cadastros_fallback(mod_short: str, builder_name: str):
    _ensure_cadastros_pkg()
    fullname = f"cadastros.{mod_short}"
    mod = sys.modules.get(fullname)
    if mod is None:
        mod = types.ModuleType(fullname)
        sys.modules[fullname] = mod
        setattr(sys.modules["cadastros"], mod_short, mod)

    if not hasattr(mod, builder_name):
        def _pick_widget(args, kwargs):
            for key in ("frm","frame","container","parent","master"):
                v = kwargs.get(key)
                if isinstance(v, (tk.Misc, ttk.Notebook, tk.Tk, tk.Toplevel)):
                    return v
            for v in reversed(args):
                if isinstance(v, (tk.Misc, ttk.Notebook, tk.Tk, tk.Toplevel)):
                    return v
            return None

        def _builder(*args, _n=mod_short, **kwargs):
            master = _pick_widget(args, kwargs)
            if master is None:
                master = tk._default_root if tk._default_root else tk.Tk()

            if isinstance(master, ttk.Notebook):
                container = ttk.Frame(master)
                try: master.add(container, text=_n.replace("_"," ").title())
                except Exception: pass
            elif isinstance(master, (tk.Tk, tk.Toplevel)):
                container = ttk.Frame(master); container.pack(fill="both", expand=True)
            else:
                container = master

            msg = ttk.Label(
                container,
                text=f"({_n} indisponível nesta instalação)\nAtualize utils\\cadastros\\{_n}.py.",
                justify="center"
            )
            msg.pack(expand=True)
            return container

        setattr(mod, builder_name, _builder)

def _handle_parametros_import_error(_e: Exception) -> bool:
    """Se 'utils.parametros' mudou de lugar, tenta fallback simples (retorna True se vale tentar de novo)."""
    return isinstance(_e, ModuleNotFoundError) or "parametros" in str(_e).lower()

# ===================== SELEÇÃO DE EMPRESA =====================
def _fmt_cnpj(cnpj):
    d = "".join(ch for ch in (cnpj or "") if ch.isdigit())
    if len(d) == 14:
        return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"
    return cnpj or ""

def _select_empresa_on_start(root) -> int | None:
    """Abre janela modal para escolher empresa. Retorna id ou None."""
    c = store._connect()
    try:
        rs = c.execute("SELECT id, COALESCE(nome, razao_social) AS nome, cnpj FROM empresas ORDER BY id").fetchall()
    finally:
        c.close()
    emps = []
    for r in rs:
        if isinstance(r, dict):
            emps.append({"id": r["id"], "nome": r["nome"], "cnpj": r["cnpj"]})
        else:
            emps.append({"id": r[0], "nome": r[1], "cnpj": r[2]})

    win = tk.Toplevel(root)
    win.title("Selecionar Empresa")

    # Ícone
    try:
        for _ico in (r"C:\nasapay\nasapay.ico",
                     os.path.join(os.path.dirname(sys.executable or ''), "nasapay.ico"),
                     os.path.join(BASE_DIR, "nasapay.ico")):
            if _ico and os.path.exists(_ico):
                win.iconbitmap(_ico)
                break
    except Exception:
        pass

    win.transient(root)
    win.grab_set()
    win.resizable(True, True)
    win.minsize(520, 360)
    win.geometry("560x380+100+80")

    ttk.Label(win, text="Escolha a empresa que deseja utilizar:",
              font=("Segoe UI", 11, "bold")).pack(pady=(12,6))

    frame = ttk.Frame(win); frame.pack(fill="both", expand=True, padx=12, pady=(0,8))
    vsb = ttk.Scrollbar(frame, orient="vertical")
    tree = ttk.Treeview(frame, columns=("nome","cnpj"), show="headings",
                        selectmode="browse", height=10, yscrollcommand=vsb.set)
    vsb.config(command=tree.yview)
    vsb.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)

    tree.heading("nome", text="Nome")
    tree.heading("cnpj", text="CNPJ")
    tree.column("nome", width=320, anchor="w")
    tree.column("cnpj", width=170, anchor="center")

    for e in emps:
        tree.insert("", "end", iid=str(e["id"]),
                    values=(e["nome"] or f"Empresa {e['id']}", _fmt_cnpj(e["cnpj"])))

    if tree.get_children():
        first = tree.get_children()[0]
        tree.selection_set(first)
        tree.focus(first)

    ttk.Label(win, text="Dica: Cadastre novas empresas no menu Cadastros.",
              foreground="#555").pack(pady=(4,0))

    chosen = {"id": None}
    def _ok(*_):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Nasapay", "Selecione uma empresa.", parent=win)
            return
        chosen["id"] = int(sel[0])
        win.destroy()
    def _cancel(*_):
        win.destroy()

    btns = ttk.Frame(win); btns.pack(pady=8)
    ttk.Button(btns, text="Usar empresa selecionada", command=_ok).pack(side="left", padx=6)
    ttk.Button(btns, text="Cancelar", command=_cancel).pack(side="left", padx=6)

    tree.bind("<Double-1>", _ok)
    win.bind("<Return>", _ok)
    win.bind("<Escape>", _cancel)

    win.wait_window()
    return chosen["id"]

# ===================== APP ========================
def iniciar_janela():
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AFS.Nasapay.App")
    except Exception:
        pass

    root = tk.Tk()

    # Ícone do app principal
    try:
        for _ico in (r"C:\nasapay\nasapay.ico",
                     os.path.join(os.path.dirname(sys.executable or ''), "nasapay.ico"),
                     os.path.join(BASE_DIR, "nasapay.ico")):
            if _ico and os.path.exists(_ico):
                root.iconbitmap(_ico)
                break
    except Exception:
        pass

    root.title("Nasapay • Remessa e Retorno • v2.0")
    try:
        root.state("zoomed")
    except Exception:
        root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    root.minsize(1100, 720)

    style = ttk.Style(root)
    try: style.theme_use("clam")
    except Exception: pass
    style.configure(".", background=MAIN_BG)
    style.configure("TFrame", background=MAIN_BG)
    style.configure("TNotebook", background=MAIN_BG)
    style.configure("TNotebook.Tab", background=MAIN_BG)

    # Barra superior e rodapé
    bar = tk.Frame(root, bg=TOP_BG, bd=1, relief="groove"); bar.pack(side="top", fill="x")
    footer = tk.Frame(root, bg=TOP_BG, bd=1, relief="flat"); footer.pack(side="bottom", fill="x")
    empresa_lbl = tk.Label(footer, text="Empresa Ativa: (não selecionada)", bg=TOP_BG, fg="#333")
    empresa_lbl.pack(side="left", padx=10, pady=4)
    rodape_txt = f"Desenvolvido por A.F.S. Consultoria • v{VERSAO} • Ano 2025"
    tk.Label(footer, text=rodape_txt, bg=footer["bg"], fg="#555").pack(side="right", padx=10, pady=4)

    # Área central
    content = tk.Frame(root, bg=MAIN_BG); content.pack(side="top", fill="both", expand=True)
    center  = tk.Frame(content, bg=MAIN_BG); center.pack(side="top", fill="both", expand=True)
    tabs = ttk.Notebook(center); tabs.pack(side="top", fill="both", expand=True, padx=8, pady=(4,8))

    # DB/migrações e empresa inicial
    store.init_db()
    eid = session.get_empresa_id()
    if not eid:
        eid = _select_empresa_on_start(root)
        if eid:
            session.set_empresa_id(eid)

    def _atualizar_footer_empresa():
        eid = session.get_empresa_id()
        if not eid:
            empresa_lbl.config(text="Empresa Ativa: (não selecionada)")
            return
        c = store._connect()
        try:
            r = c.execute("SELECT COALESCE(nome, razao_social) AS nome, cnpj FROM empresas WHERE id=?", (eid,)).fetchone()
        finally:
            c.close()
        if isinstance(r, dict):
            nome, cnpj = r.get("nome") or f"Empresa {eid}", r.get("cnpj") or ""
        else:
            nome, cnpj = (r[0] if r else f"Empresa {eid}"), (r[1] if (r and r[1]) else "")
        empresa_lbl.config(text=f"Empresa Ativa: {nome} • {_fmt_cnpj_mask(cnpj)}")
    _atualizar_footer_empresa()

    # Rodapé clicável para trocar empresa
    def _trocar_empresa(_evt=None):
        chosen = _select_empresa_on_start(root)
        if chosen:
            session.set_empresa_id(chosen)
            _atualizar_footer_empresa()
            fechar_todas()
    empresa_lbl.config(cursor="hand2")
    empresa_lbl.bind("<Button-1>", _trocar_empresa)
    empresa_lbl.bind("<Enter>", lambda e: empresa_lbl.config(fg="#0066cc"))
    empresa_lbl.bind("<Leave>", lambda e: empresa_lbl.config(fg="#333"))

    # -------- Logo central quando não há abas --------
    def _prepare_logo():
        preferred = _preferred_logo_path()
        try:
            img = Image.open(preferred).convert("RGBA") if preferred else _fallback_logo()
            img = _kill_near_white(img)
            img = img.resize((min(900, img.width), int(min(900, img.width) * img.height / img.width)), Image.LANCZOS)
            r,g,b,a = img.split(); a = a.point(lambda v: int(v * 0.5))
            img = Image.merge("RGBA", (r,g,b,a))
            return ImageTk.PhotoImage(img)
        except Exception:
            return ImageTk.PhotoImage(_fallback_logo())
    logo_img = _prepare_logo()
    logo_lbl = tk.Label(center, image=logo_img, bg=MAIN_BG, bd=0)
    def _sync_logo(_=None):
        try:
            if tabs.tabs():
                logo_lbl.place_forget()
            else:
                logo_lbl.configure(image=logo_img)
                logo_lbl.place(relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass
    tabs.bind("<<NotebookTabChanged>>", _sync_logo, add=True)
    _sync_logo()

    # -------- Abertura de cadastros (utils.parametros) --------
    def _open_cadastro(secao: str):
        tries, last = 2, None
        while tries > 0:
            tries -= 1
            try:
                from utils import parametros as _p
                if secao == "pastas":
                    import utils.cadastros.pastas_nova as pastas_nova
                    importlib.reload(pastas_nova)
                    pastas_nova.open_pastas_tab(container=tabs, add_tab=tabs.add)
                else:
                    _p.abrir_parametros(parent=root, secao=secao, container=tabs)

                _sync_logo()
                return
            except Exception as e:
                last = e
                if _handle_parametros_import_error(e):
                    for k in ("utils.parametros", "parametros"):
                        sys.modules.pop(k, None)
                    continue
                break
        messagebox.showerror("Cadastro", f"Falha ao abrir cadastros:\n{last}", parent=root)


    def fechar_todas():
        for tid in tabs.tabs():
            page = tabs.nametowidget(tid)
            if hasattr(page, "_nasapay_close"):
                page._nasapay_close(direct=True)
            else:
                tabs.forget(tid)
        _sync_logo()

    # --------------- Menus superiores ---------------
    def dd_cadastros():
        m = tk.Menu(root, tearoff=False)
        m.add_command(label="Cadastrar Nova Empresa",   command=lambda: _open_cadastro("empresa"))
        m.add_separator()
        m.add_command(label="Empresa",                  command=lambda: _open_cadastro("empresa"))
        m.add_command(label="Conta Nasapay",            command=lambda: _open_cadastro("conta_nasapay"))
        m.add_command(label="Conta E-mail",             command=lambda: _open_cadastro("conta_email"))
        m.add_command(label="Cobrança",                 command=lambda: _open_cadastro("cobranca"))
        m.add_command(label="Pastas Padrão",            command=lambda: _open_cadastro("pastas"))
        m.add_command(label="Sequenciais (NN/Remessa)", command=lambda: _open_cadastro("sequenciais"))
        # extras opcionais
        try:
            from utils.sacador_avalista import open_sacador_avalista
            m.add_command(label="Sacador/Avalista", command=lambda: (open_sacador_avalista(parent=root, container=tabs), _sync_logo()))
        except Exception:
            m.add_command(label="Sacador/Avalista (indisponível)", state="disabled")
        try:
            from utils.contas_bancarias import open_contas
            m.add_command(label="Contas Bancárias", command=lambda: (open_contas(parent=root, container=tabs), _sync_logo()))
        except Exception:
            m.add_command(label="Contas Bancárias (indisponível)", state="disabled")
        return m

    def dd_remessa():
        m = tk.Menu(root, tearoff=False)

        def _conv_xml():
            try:
                from src.conversor_xml import converter_arquivo_xml
                from utils.parametros import carregar_parametros
                parametros = carregar_parametros()
                converter_arquivo_xml(parametros)
            except Exception as e:
                messagebox.showerror("Importar XML", f"Falha: {e}", parent=root)

        def _conv_brad():
            try:
                from src.conversor_bradesco import converter_arquivo_bradesco
                from utils.parametros import carregar_parametros
                parametros = carregar_parametros()
                converter_arquivo_bradesco(parametros)
            except Exception as e:
                messagebox.showerror("Importar CNAB 400 Bradesco", f"Falha: {e}", parent=root)

        def _conv_bb240():
            try:
                from src.conversor_bb240 import converter_arquivo_bb240
                from utils.parametros import carregar_parametros
                parametros = carregar_parametros()
                converter_arquivo_bb240(parametros)
            except Exception as e:
                messagebox.showerror("Importar CNAB 240 BB", f"Falha: {e}", parent=root)

        def _validar():
            try:
                from utils.validador_remessa import open_validador_remessa
                open_validador_remessa(parent=root)
            except Exception as e:
                messagebox.showerror("Validador de Remessa", f"Falha ao abrir validador:\n{e}", parent=root)

        m.add_command(label="Conversor XML",               command=_conv_xml)
        m.add_command(label="Conversor Bradesco CNAB 400", command=_conv_brad)
        m.add_command(label="Conversor CNAB BB240",        command=_conv_bb240)
        m.add_separator()
        m.add_command(label="Validar Remessa (BMP)",       command=_validar)
        return m

    def dd_retorno():
        m = tk.Menu(root, tearoff=False)
        def _ret_bmp():
            try:
                from src.retorno_bmp import abrir_retorno_bmp_gui
                abrir_retorno_bmp_gui(root)
            except Exception as e:
                messagebox.showerror("Retorno Nasapay", f"Falha: {e}", parent=root)
        m.add_command(label="Retorno Nasapay", command=_ret_bmp)
        return m

    def dd_emitir():
        m = tk.Menu(root, tearoff=False)
        def _emitir():
            try:
                from src.boletos import imprimir_boletos
                imprimir_boletos()
            except Exception as e:
                messagebox.showerror("Gerar Boletos (PDF)", f"Falha: {e}", parent=root)
        m.add_command(label="Gerar Boleto PDF", command=_emitir)
        return m

    def dd_envio():
        m = tk.Menu(root, tearoff=False)
        fn, err = _resolve_open_envio_boletos()
        def _open(mode):
            if fn: fn(parent=root, container=tabs, modo=mode)
        if fn is None:
            m.add_command(label="(módulo de envio não encontrado)", state="disabled")
            m.add_separator()
            m.add_command(label="Diagnóstico…", command=lambda: messagebox.showinfo("Envio • Diagnóstico", err or "sem detalhes", parent=root))
            return m
        m.add_command(label="Selecionar Títulos", command=lambda: _open("sacado"))
        m.add_separator()
        m.add_command(label="Assinatura Padrão",  command=lambda: _open("assinatura"))
        m.add_command(label="Modelo de Mensagem", command=lambda: _open("modelo"))
        return m

    def dd_janelas():
        m = tk.Menu(root, tearoff=False)
        if tabs.tabs():
            for tid in tabs.tabs():
                txt = tabs.tab(tid, "text")
                m.add_command(label=txt or "(sem título)", command=lambda t=tid: tabs.select(t))
            m.add_separator()
            m.add_command(
                label="Fechar aba atual",
                command=lambda: (tabs.nametowidget(tabs.select())._nasapay_close(direct=True)
                                 if tabs.tabs() else None)
            )
            m.add_command(label="Fechar todas as abas", command=fechar_todas)
        else:
            m.add_command(label="(nenhuma aba aberta)", state="disabled")
        return m

    # Monta a barra de menus (labels clicáveis)
    MenuLabel(bar, "Cadastros", dd_cadastros).pack(side="left")
    MenuLabel(bar, "Remessa",   dd_remessa).pack(side="left")
    MenuLabel(bar, "Retorno",   dd_retorno).pack(side="left")
    MenuLabel(bar, "Emitir Boleto", dd_emitir).pack(side="left")
    MenuLabel(bar, "Enviar Boleto", dd_envio).pack(side="left")
    MenuLabel(bar, "Janelas",   dd_janelas).pack(side="left")

    root.mainloop()

if __name__ == "__main__":
    iniciar_janela()
