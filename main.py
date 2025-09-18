# main.py — Nasapay • Remessa e Retorno • v2.0 (menus + seleção empresa estáveis)
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

# Alias opcional para cadastros
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
sys.excepthook = _excepthook  # :contentReference[oaicite:5]{index=5}

# ===================== VISUAL =====================
MAIN_BG = "#ffffff"
TOP_BG  = "#f0f0f0"

def _preferred_logo_path():
    for p in (r"C:\nasapay\logo_nasapay.png",
              r"C:\nasapay\Logo Nasapay.png",
              r"C:\nasapay\Logo_nasapay.png"):
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
        m = self.dropdown() if callable(self.dropdown) else self.dropdown
        if m:
            x = self.winfo_rootx(); y = self.winfo_rooty() + self.winfo_height()
            try:    m.tk_popup(x, y)
            finally:m.grab_release()

# ===================== seleção de empresa =====================
def _select_empresa_on_start(root) -> int | None:
    c = store._connect()
    try:
        rs = c.execute("SELECT id, COALESCE(nome, razao_social) AS nome, cnpj FROM empresas ORDER BY id").fetchall()
    finally:
        c.close()
    win = tk.Toplevel(root)
    win.title("Selecionar Empresa")
    try:
        for _ico in (r"C:\nasapay\nasapay.ico",
                     os.path.join(os.path.dirname(sys.executable or ''), "nasapay.ico"),
                     os.path.join(BASE_DIR, "nasapay.ico")):
            if _ico and os.path.exists(_ico):
                win.iconbitmap(_ico); break
    except Exception: pass
    win.transient(root); win.grab_set(); win.resizable(True, True)
    ttk.Label(win, text="Escolha a empresa:", font=("Segoe UI", 11, "bold")).pack(pady=(12,6))
    frame = ttk.Frame(win); frame.pack(fill="both", expand=True, padx=12, pady=(0,8))
    vsb = ttk.Scrollbar(frame, orient="vertical")
    tree = ttk.Treeview(frame, columns=("nome","cnpj"), show="headings",
                        selectmode="browse", height=10, yscrollcommand=vsb.set)
    vsb.config(command=tree.yview); vsb.pack(side="right", fill="y")
    tree.pack(side="left", fill="both", expand=True)
    tree.heading("nome", text="Nome"); tree.heading("cnpj", text="CNPJ")
    tree.column("nome", width=320, anchor="w"); tree.column("cnpj", width=170, anchor="center")
    for r in rs:
        nome = r["nome"] if isinstance(r, dict) else r[1]
        cnpj = r["cnpj"] if isinstance(r, dict) else r[2]
        tree.insert("", "end", iid=str(r["id"] if isinstance(r, dict) else r[0]),
                    values=(nome or "(sem nome)", _fmt_cnpj_mask(cnpj)))
    if tree.get_children():
        first = tree.get_children()[0]; tree.selection_set(first); tree.focus(first)
    chosen = {"id": None}
    def _ok(*_):
        sel = tree.selection()
        if not sel:
            messagebox.showwarning("Nasapay", "Selecione uma empresa.", parent=win); return
        chosen["id"] = int(sel[0]); win.destroy()
    def _cancel(*_): win.destroy()
    btns = ttk.Frame(win); btns.pack(pady=8)
    ttk.Button(btns, text="Usar", command=_ok).pack(side="left", padx=6)
    ttk.Button(btns, text="Cancelar", command=_cancel).pack(side="left", padx=6)
    tree.bind("<Double-1>", _ok); win.bind("<Return>", _ok); win.bind("<Escape>", _cancel)
    win.wait_window(); return chosen["id"]

# ===================== app =====================
def iniciar_janela():
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AFS.Nasapay.App")
    except Exception:
        pass

    root = tk.Tk()
    try:
        for _ico in (r"C:\nasapay\nasapay.ico",
                     os.path.join(os.path.dirname(sys.executable or ''), "nasapay.ico"),
                     os.path.join(BASE_DIR, "nasapay.ico")):
            if _ico and os.path.exists(_ico):
                root.iconbitmap(_ico); break
    except Exception:
        pass

    root.title("Nasapay • Remessa e Retorno • v2.0")
    try: root.state("zoomed")
    except Exception: root.geometry(f"{root.winfo_screenwidth()}x{root.winfo_screenheight()}+0+0")
    root.minsize(1100, 720)

    style = ttk.Style(root)
    try: style.theme_use("clam")
    except Exception: pass
    style.configure(".", background=MAIN_BG)
    style.configure("TFrame", background=MAIN_BG)
    style.configure("TNotebook", background=MAIN_BG)
    style.configure("TNotebook.Tab", background=MAIN_BG)

    bar = tk.Frame(root, bg=TOP_BG, bd=1, relief="groove"); bar.pack(side="top", fill="x")
    footer = tk.Frame(root, bg=TOP_BG, bd=1, relief="flat"); footer.pack(side="bottom", fill="x")
    empresa_lbl = tk.Label(footer, text="Empresa Ativa: (não selecionada)", bg=TOP_BG, fg="#333")
    empresa_lbl.pack(side="left", padx=10, pady=4)
    tk.Label(footer, text=f"Desenvolvido por A.F.S. Consultoria • v{VERSAO} • Ano 2025",
             bg=footer["bg"], fg="#555").pack(side="right", padx=10, pady=4)

    content = tk.Frame(root, bg=MAIN_BG); content.pack(side="top", fill="both", expand=True)
    center  = tk.Frame(content, bg=MAIN_BG); center.pack(side="top", fill="both", expand=True)
    tabs = ttk.Notebook(center); tabs.pack(side="top", fill="both", expand=True, padx=8, pady=(4,8))

    store.init_db()
    eid = session.get_empresa_id() or _select_empresa_on_start(root)
    if eid: session.set_empresa_id(eid)

    def _atualizar_footer():
        eid = session.get_empresa_id()
        if not eid:
            empresa_lbl.config(text="Empresa Ativa: (não selecionada)"); return
        c = store._connect()
        try:
            r = c.execute("SELECT COALESCE(nome, razao_social) AS nome, cnpj FROM empresas WHERE id=?", (eid,)).fetchone()
        finally:
            c.close()
        if isinstance(r, dict):
            nome, cnpj = r.get("nome") or f"Empresa {eid}", r.get("cnpj") or ""
        else:
            nome, cnpj = (r[0] if r else f"Empresa {eid}"), (r[1] if r else "")
        empresa_lbl.config(text=f"Empresa Ativa: {nome} • {_fmt_cnpj_mask(cnpj)}")
    _atualizar_footer()

    def fechar_todas():
        for tid in tabs.tabs():
            tabs.forget(tid)

    def _trocar_empresa(_=None):
        new_id = _select_empresa_on_start(root)
        if new_id:
            session.set_empresa_id(new_id)
            _atualizar_footer()
            fechar_todas()
    empresa_lbl.config(cursor="hand2")
    empresa_lbl.bind("<Button-1>", _trocar_empresa)
    empresa_lbl.bind("<Enter>", lambda e: empresa_lbl.config(fg="#0066cc"))
    empresa_lbl.bind("<Leave>", lambda e: empresa_lbl.config(fg="#333"))

    # Logo central quando não há abas
    def _prepare_logo():
        pref = _preferred_logo_path()
        try:
            img = Image.open(pref).convert("RGBA") if pref else _fallback_logo()
            img = _kill_near_white(img)
            img = img.resize((min(900, img.width), int(min(900, img.width)*img.height/img.width)), Image.LANCZOS)
            r,g,b,a = img.split(); a = a.point(lambda v: int(v*0.5))
            return ImageTk.PhotoImage(Image.merge("RGBA",(r,g,b,a)))
        except Exception:
            return ImageTk.PhotoImage(_fallback_logo())
    logo_img = _prepare_logo()
    logo_lbl = tk.Label(center, image=logo_img, bg=MAIN_BG, bd=0)
    def _sync_logo(_=None):
        try:
            if tabs.tabs(): logo_lbl.place_forget()
            else:           logo_lbl.configure(image=logo_img); logo_lbl.place(relx=0.5, rely=0.5, anchor="center")
        except Exception: pass
    tabs.bind("<<NotebookTabChanged>>", _sync_logo, add=True); _sync_logo()

    # -------- Cadastros (usa utils.parametros.abrir_parametros) --------
    def _open_cadastro(secao: str):
        try:
            from utils import parametros as _p
            _p.abrir_parametros(parent=root, secao=secao, container=tabs)
            _sync_logo()
        except Exception as e:
            messagebox.showerror("Cadastro", f"Falha ao abrir cadastros:\n{e}", parent=root)

    # ---------------- Menus ----------------
    def dd_cadastros():
        m = tk.Menu(root, tearoff=False)
        m.add_command(label="Empresa",                  command=lambda: _open_cadastro("empresa"))
        m.add_command(label="Conta Nasapay",            command=lambda: _open_cadastro("conta_nasapay"))
        m.add_command(label="Conta E-mail",             command=lambda: _open_cadastro("conta_email"))
        m.add_separator()
        m.add_command(label="Cobrança",                 command=lambda: _open_cadastro("cobranca"))
        m.add_command(label="Pastas Padrão",            command=lambda: _open_cadastro("pastas"))
        m.add_command(label="Sequenciais (NN/Remessa)", command=lambda: _open_cadastro("sequenciais"))
        return m

    def dd_remessa():
        m = tk.Menu(root, tearoff=False)
        def _conv_xml():
            try:
                from src.conversor_xml import converter_arquivo_xml
                converter_arquivo_xml()
            except Exception as e:
                messagebox.showerror("Importar XML", f"Falha: {e}", parent=root)
        def _conv_brad():
            try:
                from src.conversor_bradesco import converter_arquivo_bradesco
                converter_arquivo_bradesco()
            except Exception as e:
                messagebox.showerror("Importar CNAB 400 Bradesco", f"Falha: {e}", parent=root)
        def _conv_bb240():
            try:
                from src.conversor_bb240 import converter_arquivo_bb240
                converter_arquivo_bb240()
            except Exception as e:
                messagebox.showerror("Importar CNAB 240 BB", f"Falha: {e}", parent=root)
        def _validar():
            try:
                from utils.validador_remessa import validar_arquivo_remessa
            except Exception as e:
                messagebox.showerror("Validador de Remessa", f"Falha ao carregar validador:\n{e}", parent=root); return
            arq = filedialog.askopenfilename(
                parent=root, title="Selecione a remessa para validar",
                filetypes=[("Remessas BMP/REM", "*.REM *.TXT *.BMP"), ("Todos", "*.*")]
            )
            if not arq: return
            try: validar_arquivo_remessa(arq, parent=root)
            except Exception as e: messagebox.showerror("Validador de Remessa", f"Falha: {e}", parent=root)
        m.add_command(label="Conversor XML",               command=_conv_xml)
        m.add_command(label="Conversor Bradesco CNAB 400", command=_conv_brad)
        m.add_command(label="Conversor CNAB BB240",        command=_conv_bb240)
        m.add_separator()
        m.add_command(label="Validar Remessa (BMP)",       command=_validar)
        return m

    def dd_outros():
        m = tk.Menu(root, tearoff=False)
        m.add_command(label="Cobranca",       command=lambda: _open_cadastro("cobranca"))
        m.add_command(label="Pastas Padrão",  command=lambda: _open_cadastro("pastas"))
        m.add_command(label="Sequenciais",    command=lambda: _open_cadastro("sequenciais"))
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
                messagebox.showerror("Gerar Boleto (PDF)", f"Falha: {e}", parent=root)
        m.add_command(label="Gerar Boleto PDF", command=_emitir)
        return m

    def dd_envio():
        m = tk.Menu(root, tearoff=False)
        try:
            from utils.ui_envio import open_envio_boletos
            m.add_command(label="Selecionar Títulos", command=lambda: open_envio_boletos(parent=root, container=tabs, modo="sacado"))
        except Exception:
            m.add_command(label="Selecionar Títulos (indisponível)", state="disabled")
        return m

    def dd_janelas():
        m = tk.Menu(root, tearoff=False)
        if tabs.tabs():
            for tid in tabs.tabs():
                txt = tabs.tab(tid, "text")
                m.add_command(label=txt or "(sem título)", command=lambda t=tid: tabs.select(t))
            m.add_separator()
            m.add_command(label="Fechar aba atual", command=lambda: tabs.forget(tabs.select()))
            m.add_command(label="Fechar todas as abas", command=fechar_todas)
        else:
            m.add_command(label="(nenhuma aba aberta)", state="disabled")
        return m

    MenuLabel(bar, "Cadastros",    dd_cadastros).pack(side="left")
    MenuLabel(bar, "Remessa",      dd_remessa).pack(side="left")
    MenuLabel(bar, "Retorno",      dd_retorno).pack(side="left")
    MenuLabel(bar, "Emitir Boleto",dd_emitir).pack(side="left")
    MenuLabel(bar, "Enviar Boleto",dd_envio).pack(side="left")
    MenuLabel(bar, "Janelas",      dd_janelas).pack(side="left")
    MenuLabel(bar, "Outros",       dd_outros).pack(side="left")  # voltou

    root.mainloop()

if __name__ == "__main__":
    iniciar_janela()
