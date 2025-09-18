import json, os, tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Mantém seu caminho atual (retrocompat)
CONFIG_PATH = os.path.abspath(os.path.join("C:/nasapay", "config.json"))

# --------------------------------------------------------------------------------------
# Utilidades básicas de configuração
# --------------------------------------------------------------------------------------
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

# --------------------------------------------------------------------------------------
# Rótulos NOVOS (visíveis para o usuário) e chaves internas (retrocompat)
# --------------------------------------------------------------------------------------
ROTULOS = [
    ("Pasta de Arquivos para Importar x Converter", "pasta_importar_remessa"),
    ("Pasta para Salvar Remessa Nasapay",           "pasta_remessa_nasapay"),
    ("Pasta para Salvar Retorno Nasapay",           "pasta_retorno_nasapay"),
    ("Pasta para Salvar Boleto PDF Gerado",         "pasta_boletos"),
]

def _aplicar_defaults_e_retrocompat(cfg: dict):
    # Mantém os campos antigos funcionando
    cfg.setdefault("pasta_importar_remessa", cfg.get("pasta_entrada", ""))
    cfg.setdefault("pasta_remessa_nasapay",  cfg.get("pasta_saida",   ""))
    cfg.setdefault("pasta_retorno_nasapay",  cfg.get("pasta_retorno_nasapay", ""))
    cfg.setdefault("pasta_boletos",          cfg.get("pasta_boletos", "C:/nasapay/boletos"))

    # Espelha legado sempre que possível
    cfg["pasta_entrada"] = cfg.get("pasta_importar_remessa", "")
    cfg["pasta_saida"]   = cfg.get("pasta_remessa_nasapay",  "")

# --------------------------------------------------------------------------------------
# NOVO: usado por telas modernas (ex.: parametros.build_aba_pastas chama isso)
# --------------------------------------------------------------------------------------
def build_aba_pastas(parent, state):
    """
    parent: Frame onde a aba será montada
    state:  helper com .cfg (dict) e .var(key)->StringVar
    """
    cfg = state.cfg
    _aplicar_defaults_e_retrocompat(cfg)

    frm = ttk.Frame(parent)
    frm.columnconfigure(1, weight=1)

    # Controle de mudança
    _snapshot = {}

    def _espelhar_legado():
        cfg["pasta_entrada"] = state.var("pasta_importar_remessa").get()
        cfg["pasta_saida"]   = state.var("pasta_remessa_nasapay").get()

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
                _espelhar_legado()

        def _on_write(*_):
            _espelhar_legado()

        var.trace_add("write", _on_write)
        ttk.Button(frm, text="Selecionar…", command=escolher).grid(row=row, column=2, padx=8, pady=6)

    # Monta as 4 linhas com rótulos novos
    for i, (rotulo, chave) in enumerate(ROTULOS):
        # Inicializa state.var com valor atual
        if not hasattr(state, "_vars"):
            state._vars = {}
        if chave not in state._vars:
            v = tk.StringVar(value=cfg.get(chave, ""))
            state._vars[chave] = v
        _linha(i, rotulo, chave)
        _snapshot[chave] = state._vars[chave].get()

    def houve_alteracao():
        for _, chave in ROTULOS:
            if state._vars[chave].get() != _snapshot[chave]:
                return True
        return False

    def salvar():
        for _, chave in ROTULOS:
            cfg[chave] = state._vars[chave].get().strip()

        # Espelho legado
        cfg["pasta_entrada"] = cfg["pasta_importar_remessa"]
        cfg["pasta_saida"]   = cfg["pasta_remessa_nasapay"]

        # Garante que as pastas existem
        for _, chave in ROTULOS:
            _garante_pasta(cfg.get(chave, ""))

        _salvar_config(cfg)
        messagebox.showinfo("Pastas", "Pastas salvas com sucesso.")
        # Fecha a aba/janela após salvar
        if hasattr(frm, "_nasapay_close"):
            frm._nasapay_close(direct=True)
        else:
            try:
                frm.master.destroy()
            except Exception:
                try:
                    frm.destroy()
                except Exception:
                    pass

    def fechar():
        if houve_alteracao():
            if messagebox.askyesno("Confirmar", "Deseja salvar antes de fechar?"):
                salvar()
                return
        # Apenas fecha
        if hasattr(frm, "_nasapay_close"):
            frm._nasapay_close(direct=True)
        else:
            try:
                frm.master.destroy()
            except Exception:
                try:
                    frm.destroy()
                except Exception:
                    pass

    # Barra de botões (ESQUERDA, abaixo dos campos)
    btns = ttk.Frame(frm)
    btns.grid(row=len(ROTULOS), column=0, columnspan=3, sticky="w", padx=8, pady=10)
    ttk.Button(btns, text="Salvar", command=salvar).grid(row=0, column=0, padx=6)
    ttk.Button(btns, text="Fechar", command=fechar).grid(row=0, column=1, padx=6)

    return frm

# --------------------------------------------------------------------------------------
# LEGADO: aba criada diretamente aqui (mantido por compatibilidade)
# --------------------------------------------------------------------------------------
def open_pastas_tab(container, add_tab):
    cfg = _carregar_config()
    _aplicar_defaults_e_retrocompat(cfg)

    frame = ttk.Frame(container)
    add_tab("Pastas Padrão", frame)
    frame.columnconfigure(1, weight=1)

    valores_iniciais = {}

    def linha_pasta(row, rotulo, chave):
        ttk.Label(frame, text=rotulo + ":").grid(row=row, column=0, sticky="e", padx=8, pady=6)
        var = tk.StringVar(value=cfg.get(chave, ""))
        valores_iniciais[chave] = var.get()

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

    # 4 linhas com rótulos NOVOS
    v_in  = linha_pasta(0, "Pasta de Arquivos para Importar x Converter", "pasta_importar_remessa")
    v_out = linha_pasta(1, "Pasta para Salvar Remessa Nasapay",          "pasta_remessa_nasapay")
    v_ret = linha_pasta(2, "Pasta para Salvar Retorno Nasapay",           "pasta_retorno_nasapay")
    v_bol = linha_pasta(3, "Pasta para Salvar Boleto PDF Gerado",         "pasta_boletos")

    def houve_alteracao():
        return any([
            v_in.get()  != valores_iniciais["pasta_importar_remessa"],
            v_out.get() != valores_iniciais["pasta_remessa_nasapay"],
            v_ret.get() != valores_iniciais["pasta_retorno_nasapay"],
            v_bol.get() != valores_iniciais["pasta_boletos"],
        ])

    def salvar():
        cfg["pasta_importar_remessa"] = v_in.get().strip()
        cfg["pasta_remessa_nasapay"]  = v_out.get().strip()
        cfg["pasta_retorno_nasapay"]  = v_ret.get().strip()
        cfg["pasta_boletos"]          = v_bol.get().strip()

        # Espelho legado
        cfg["pasta_entrada"] = cfg["pasta_importar_remessa"]
        cfg["pasta_saida"]   = cfg["pasta_remessa_nasapay"]

        for pth in (
            cfg["pasta_importar_remessa"],
            cfg["pasta_remessa_nasapay"],
            cfg["pasta_retorno_nasapay"],
            cfg["pasta_boletos"],
        ):
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

    def fechar():
        if houve_alteracao():
            if messagebox.askyesno("Confirmar", "Deseja salvar antes de fechar?", parent=frame):
                salvar()
                return
        try:
            frame.destroy()
        except Exception:
            pass

    # Botões à ESQUERDA, logo abaixo do último campo
    btns = ttk.Frame(frame); btns.grid(row=4, column=0, columnspan=3, sticky="w", padx=8, pady=10)
    ttk.Button(btns, text="Salvar", command=salvar).grid(row=0, column=0, padx=6)
    ttk.Button(btns, text="Fechar", command=fechar).grid(row=0, column=1, padx=6)
