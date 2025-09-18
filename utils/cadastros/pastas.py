# utils/cadastros/pastas.py
import json, os, tkinter as tk
from tkinter import ttk, filedialog, messagebox

CONFIG_PATH = os.path.abspath(os.path.join("C:/nasapay", "config.json"))

def _carregar_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _salvar_config(cfg: dict):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def _garante_pasta(p: str):
    if p and not os.path.isdir(p):
        os.makedirs(p, exist_ok=True)

# ---------------- NOVO (usado por parametros.build_aba_pastas) ----------------
def build_aba_pastas(parent, state):
    """
    parent: Frame onde a aba será montada
    state:  helper com .cfg (dict) e .var(key)->StringVar
    """
    cfg = state.cfg

    # Defaults e retrocompat
    cfg.setdefault("pasta_importar_remessa", cfg.get("pasta_entrada", ""))
    cfg.setdefault("pasta_remessa_nasapay",  cfg.get("pasta_saida",   ""))
    cfg.setdefault("pasta_retorno_nasapay",  cfg.get("pasta_retorno_nasapay", ""))
    cfg.setdefault("pasta_boletos",          cfg.get("pasta_boletos", "C:/nasapay/boletos"))

    frm = ttk.Frame(parent)
    frm.columnconfigure(1, weight=1)

    def _espelha_legado():
        cfg["pasta_entrada"] = cfg.get("pasta_importar_remessa", "")
        cfg["pasta_saida"]   = cfg.get("pasta_remessa_nasapay",  "")

    def _linha(row, rotulo, chave):
        ttk.Label(frm, text=rotulo + ":").grid(row=row, column=0, sticky="e", padx=8, pady=6)
        var = state.var(chave)
        ent = ttk.Entry(frm, textvariable=var, width=70)
        ent.grid(row=row, column=1, sticky="we", padx=8, pady=6)
        def escolher():
            ini = var.get() or os.path.expanduser("~")
            pasta = filedialog.askdirectory(initialdir=ini, title=rotulo, parent=frm)
            if pasta:
                var.set(pasta)
                _garante_pasta(pasta)
                _espelha_legado()
        def _on_write(*_):
            _espelha_legado()
        var.trace_add("write", _on_write)
        ttk.Button(frm, text="Selecionar…", command=escolher).grid(row=row, column=2, padx=8, pady=6)

    _linha(0, "Pasta Importar Remessa", "pasta_importar_remessa")
    _linha(1, "Pasta Remessa Nasapay",  "pasta_remessa_nasapay")
    _linha(2, "Pasta Retorno Nasapay",  "pasta_retorno_nasapay")
    _linha(3, "Pasta Boletos",          "pasta_boletos")

    _espelha_legado()
    return frm

# ---------------- LEGADO (aba criada diretamente aqui) ----------------
def open_pastas_tab(container, add_tab):
    cfg = _carregar_config()
    cfg.setdefault("pasta_importar_remessa", cfg.get("pasta_entrada", ""))
    cfg.setdefault("pasta_remessa_nasapay",  cfg.get("pasta_saida",   ""))
    cfg.setdefault("pasta_retorno_nasapay",  cfg.get("pasta_retorno_nasapay", ""))
    cfg.setdefault("pasta_boletos",          cfg.get("pasta_boletos", "C:/nasapay/boletos"))

    frame = ttk.Frame(container)
    add_tab("Pastas Padrão", frame)
    frame.columnconfigure(1, weight=1)

    def linha_pasta(row, rotulo, chave):
        ttk.Label(frame, text=rotulo + ":").grid(row=row, column=0, sticky="e", padx=8, pady=6)
        var = tk.StringVar(value=cfg.get(chave, ""))
        ent = ttk.Entry(frame, textvariable=var, width=70)
        ent.grid(row=row, column=1, sticky="we", padx=8, pady=6)
        def escolher():
            ini = var.get() or os.path.expanduser("~")
            pasta = filedialog.askdirectory(initialdir=ini, title=rotulo, parent=frame)
            if pasta:
                var.set(pasta)
                _garante_pasta(pasta)
        ttk.Button(frame, text="Selecionar…", command=escolher).grid(row=row, column=2, padx=8, pady=6)
        return var

    v_in  = linha_pasta(0, "Pasta Importar Remessa", "pasta_importar_remessa")
    v_out = linha_pasta(1, "Pasta Remessa Nasapay",  "pasta_remessa_nasapay")
    v_ret = linha_pasta(2, "Pasta Retorno Nasapay",  "pasta_retorno_nasapay")
    v_bol = linha_pasta(3, "Pasta Boletos",          "pasta_boletos")

    def salvar():
        cfg["pasta_importar_remessa"] = v_in.get().strip()
        cfg["pasta_remessa_nasapay"]  = v_out.get().strip()
        cfg["pasta_retorno_nasapay"]  = v_ret.get().strip()
        cfg["pasta_boletos"]          = v_bol.get().strip()
        # espelho legado
        cfg["pasta_entrada"] = cfg["pasta_importar_remessa"]
        cfg["pasta_saida"]   = cfg["pasta_remessa_nasapay"]
        for pth in (cfg["pasta_importar_remessa"], cfg["pasta_remessa_nasapay"], cfg["pasta_retorno_nasapay"], cfg["pasta_boletos"]):
            _garante_pasta(pth)
    _salvar_config(cfg)
        messagebox.showinfo("Pastas", "Pastas salvas com sucesso.", parent=frame)
        
    # fecha a aba/janela após salvar
        if hasattr(frame, "_nasapay_close"):
            frame._nasapay_close(direct=True)
        else:
            try:
                frame.destroy()
            except Exception:
                pass

    btns = ttk.Frame(frame); btns.grid(row=4, column=0, columnspan=3, sticky="e", padx=8, pady=10)
    ttk.Button(btns, text="Salvar", command=salvar).grid(row=0, column=0, padx=6)
    ttk.Button(btns, text="Fechar", command=lambda: frame.destroy()).grid(row=0, column=1, padx=6)
