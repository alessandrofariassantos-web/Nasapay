# utils/parametros.py — UI Cadastros (layout clássico) + API (v2.0)
from __future__ import annotations
import sqlite3, re
from typing import Dict
import tkinter as tk
from tkinter import ttk, messagebox

from utils import store, session

# ------------------ helpers ------------------
_DIGIT_RE = re.compile(r"\D")

def _digits(s: str | None, limit: int | None = None) -> str:
    s = _DIGIT_RE.sub("", s or "")
    return s[:limit] if (limit and limit > 0) else s

def _mask_cnpj(s: str | None) -> str:
    d = _digits(s, 14).rjust(14, "0") if s else ""
    if len(d) != 14: return s or ""
    return f"{d[0:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}"

def _mask_tel(s: str | None) -> str:
    d = _digits(s, 11)
    if len(d) == 11: return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    if len(d) == 10: return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    return s or ""

# ------------------ storage (K/V por seção) ------------------
def _ensure_param_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parametros(
            empresa_id INTEGER NOT NULL,
            secao      TEXT    NOT NULL,
            chave      TEXT    NOT NULL,
            valor      TEXT,
            PRIMARY KEY (empresa_id, secao, chave)
        )
    """)
    conn.commit()

# ------------------ API pública (conversores/gerador usam) ---
def carregar_parametros() -> Dict[str, str]:
    eid = session.get_empresa_id()
    if not eid:
        return {}
    con = store._connect()
    try:
        _ensure_param_table(con)
        rows = con.execute("""
            SELECT secao, chave, COALESCE(valor,'') AS valor
              FROM parametros
             WHERE empresa_id = ?
             ORDER BY secao, chave
        """, (eid,)).fetchall()
        cfg: Dict[str, str] = {r["chave"]: r["valor"] for r in rows}
        r = con.execute(
            "SELECT COALESCE(nome, razao_social) AS nome, razao_social, cnpj, endereco, cidade, uf, cep, telefone, email "
            "FROM empresas WHERE id=?",
            (eid,)
        ).fetchone()
        if r:
            cfg.setdefault("razao_social", (r["razao_social"] or r["nome"] or "").strip())
            cfg.setdefault("cnpj",        r["cnpj"] or "")
            cfg.setdefault("endereco",    r["endereco"] or "")
            cfg.setdefault("cidade",      r["cidade"] or "")
            cfg.setdefault("uf",          (r["uf"] or "")[:2])
            cfg.setdefault("cep",         r["cep"] or "")
            cfg.setdefault("telefone",    r["telefone"] or "")
            cfg.setdefault("email",       r["email"] or "")
        return cfg
    finally:
        con.close()

def salvar_parametros(cfg: Dict[str, str]) -> None:
    if not cfg: return
    eid = session.get_empresa_id()
    if not eid: return
    con = store._connect()
    try:
        _ensure_param_table(con)

        # Empresa (quando vier)
        if any(k in cfg for k in ("razao_social","cnpj","endereco","cidade","uf","cep","telefone","email")):
            up = {
                "razao_social": (cfg.get("razao_social") or "").strip().upper(),
                "cnpj":         _digits(cfg.get("cnpj"), 14),
                "endereco":     (cfg.get("endereco") or "").strip().upper(),
                "cidade":       (cfg.get("cidade") or "").strip().upper(),
                "uf":           (cfg.get("uf") or "").strip().upper()[:2],
                "cep":          _digits(cfg.get("cep"), 8),
                "telefone":     _digits(cfg.get("telefone"), 11),
                "email":        (cfg.get("email") or "").strip(),
            }
            con.execute("""
                UPDATE empresas
                   SET razao_social=:razao_social, cnpj=:cnpj, endereco=:endereco,
                       cidade=:cidade, uf=:uf, cep=:cep, telefone=:telefone, email=:email
                 WHERE id=:id
            """, {**up, "id": eid})

        # Sequenciais (NN / remessa)
        def _save_pair(secao, chave, valor):
            con.execute(
                """
                INSERT INTO parametros(empresa_id,secao,chave,valor)
                VALUES (?,?,?,?)
                ON CONFLICT(empresa_id,secao,chave) DO UPDATE SET valor=excluded.valor
                """,
                (eid, secao, chave, valor or "")
            )

        if "nosso_numero" in cfg:
            _save_pair("sequenciais", "nosso_numero", _digits(cfg.get("nosso_numero"), 11).rjust(11, "0"))
        if "ultima_remessa" in cfg:
            _save_pair("sequenciais", "ultima_remessa", _digits(cfg.get("ultima_remessa"), 7).rjust(7, "0"))

        # Pastas
        for k,v in (cfg or {}).items():
            if k.startswith(("pasta_", "pastas_")):
                _save_pair("pastas", k, v or "")

        con.commit()
    finally:
        con.close()

def gerar_nosso_numero(cfg: Dict[str,str] | None = None) -> str:
    eid = session.get_empresa_id()
    if not eid: return "00000000001"
    con = store._connect()
    try:
        _ensure_param_table(con)
        row = con.execute(
            "SELECT valor FROM parametros WHERE empresa_id=? AND secao='sequenciais' AND chave='nosso_numero'",
            (eid,)
        ).fetchone()
        atual = int(_digits(row["valor"]) or "0") if row else 0
        prox  = max(0, atual) + 1
        con.execute(
            """
            INSERT INTO parametros(empresa_id,secao,chave,valor)
            VALUES (?,?,?,?)
            ON CONFLICT(empresa_id,secao,chave) DO UPDATE SET valor=excluded.valor
            """,
            (eid, "sequenciais", "nosso_numero", f"{prox:011d}")
        )
        con.commit()
        if isinstance(cfg, dict):
            cfg["nosso_numero"] = f"{prox:011d}"
        return f"{prox:011d}"
    finally:
        con.close()

# ------------------ UI (layout clássico) ------------------
_TITULOS = {
    "empresa":        "Empresa",
    "conta_nasapay":  "Conta_Nasapay",
    "conta_email":    "Conta_Email",
    "cobranca":       "Cobranca",
    "pastas":         "Pastas Padrão",
    "sequenciais":    "Sequenciais (NN/Remessa)",
}

def _load_cfg(empresa_id: int, secao: str) -> dict:
    con = store._connect()
    try:
        if secao == "empresa":
            r = con.execute(
                "SELECT COALESCE(nome, razao_social) AS nome, razao_social, cnpj, endereco, cidade, uf, cep, telefone, email "
                "FROM empresas WHERE id=?",
                (empresa_id,)
            ).fetchone()
            if not r: return {}
            return {
                "razao_social": (r["razao_social"] or r["nome"] or "").strip(),
                "cnpj":        _mask_cnpj(r["cnpj"] or ""),
                "endereco":    r["endereco"] or "",
                "cidade":      r["cidade"] or "",
                "uf":          (r["uf"] or "")[:2],
                "cep":         r["cep"] or "",
                "telefone":    _mask_tel(r["telefone"] or ""),
                "email":       r["email"] or "",
            }
        _ensure_param_table(con)
        rows = con.execute(
            "SELECT chave, valor FROM parametros WHERE empresa_id=? AND secao=?",
            (empresa_id, secao)
        ).fetchall()
        return {r["chave"]: (r["valor"] or "") for r in rows}
    finally:
        con.close()

def _save_cfg(empresa_id: int, secao: str, data: dict) -> None:
    con = store._connect()
    try:
        if secao == "empresa":
            up = {
                "razao_social": (data.get("razao_social") or "").strip().upper(),
                "cnpj":         _digits(data.get("cnpj"), 14),
                "endereco":     (data.get("endereco") or "").strip().upper(),
                "cidade":       (data.get("cidade") or "").strip().upper(),
                "uf":           (data.get("uf") or "").strip().upper()[:2],
                "cep":          _digits(data.get("cep"), 8),
                "telefone":     _digits(data.get("telefone"), 11),
                "email":        (data.get("email") or "").strip(),
            }
            con.execute("""
                UPDATE empresas
                   SET razao_social=:razao_social, cnpj=:cnpj, endereco=:endereco,
                       cidade=:cidade, uf=:uf, cep=:cep, telefone=:telefone, email=:email
                 WHERE id=:id
            """, {**up, "id": empresa_id})
            con.commit()
            return

        _ensure_param_table(con)
        for k, v in (data or {}).items():
            con.execute(
                """
                INSERT INTO parametros(empresa_id,secao,chave,valor)
                VALUES (?,?,?,?)
                ON CONFLICT(empresa_id,secao,chave) DO UPDATE SET valor=excluded.valor
                """,
                (empresa_id, secao, k, str(v or ""))
            )
        con.commit()
    finally:
        con.close()

def _mk_entry(frm, label, var, width=50, row=None, col=0, padx=(6,6), pady=(4,4)):
    ttk.Label(frm, text=label).grid(row=row, column=col, sticky="w", padx=padx, pady=pady)
    ent = ttk.Entry(frm, textvariable=var, width=width)
    ent.grid(row=row, column=col+1, sticky="w", padx=padx, pady=pady)
    return ent

def abrir_parametros(parent=None, secao: str="empresa", container=None):
    """
    Abre a tela de parâmetros numa aba (quando container é Notebook) ou numa Toplevel.
    Botões 'Salvar' e 'Fechar' ficam JUNTOS abaixo dos campos.
    'Salvar' grava e FECHA a aba/janela.
    """
    eid = session.get_empresa_id()
    if not eid:
        messagebox.showwarning("Parâmetros", "Selecione uma empresa antes.", parent=parent)
        return

    title = _TITULOS.get(secao, secao.title())
    data  = _load_cfg(eid, secao)

    # onde renderizar
    toplevel = None
    if isinstance(container, ttk.Notebook):
        page = ttk.Frame(container)
        container.add(page, text=title)
        container.select(page)
        host = page
        # grid padrão (sem expandir os entries)
        host.columnconfigure(0, weight=0)
        host.columnconfigure(1, weight=0)
    else:
        toplevel = tk.Toplevel(parent)
        toplevel.title(title)
        toplevel.minsize(640, 360)
        host = toplevel

    frm = ttk.Frame(host)
    frm.pack(fill="both", expand=True, padx=12, pady=10)
    # NÃO expandir a coluna dos entries: mantém largura “coerente”, não tela cheia
    frm.grid_columnconfigure(0, weight=0)
    frm.grid_columnconfigure(1, weight=0)

    vars = {k: tk.StringVar(value=str(v or "")) for k, v in data.items()}

    if secao == "empresa":
        for key in ("razao_social","cnpj","endereco","cidade","uf","cep","telefone","email"):
            vars.setdefault(key, tk.StringVar(value=data.get(key, "")))

        e1 = _mk_entry(frm, "Razão Social", vars["razao_social"], width=80, row=0)
        e2 = _mk_entry(frm, "CNPJ",         vars["cnpj"],         width=28, row=1)
        e3 = _mk_entry(frm, "Endereço",     vars["endereco"],     width=80, row=2)
        e4 = _mk_entry(frm, "Cidade",       vars["cidade"],       width=40, row=3)
        e5 = _mk_entry(frm, "UF",           vars["uf"],           width=6,  row=4)
        e6 = _mk_entry(frm, "CEP",          vars["cep"],          width=16, row=5)
        e7 = _mk_entry(frm, "Telefone",     vars["telefone"],     width=22, row=6)
        e8 = _mk_entry(frm, "E-mail",       vars["email"],        width=60, row=7)

        # formatações ao sair do campo
        def _fmt_cnpj_evt(_=None): vars["cnpj"].set(_mask_cnpj(vars["cnpj"].get()))
        def _fmt_tel_evt(_=None):  vars["telefone"].set(_mask_tel(vars["telefone"].get()))
        e2.bind("<FocusOut>", _fmt_cnpj_evt)
        e7.bind("<FocusOut>", _fmt_tel_evt)

    elif secao == "pastas":
        for key in ("pasta_importar_remessa","pasta_entrada","pasta_saida","pastas_pdf","pastas_baixados"):
            vars.setdefault(key, tk.StringVar(value=data.get(key, "")))
        _mk_entry(frm, "Pasta importar remessa", vars["pasta_importar_remessa"], width=80, row=0)
        _mk_entry(frm, "Pasta entrada (legado)", vars["pasta_entrada"],         width=80, row=1)
        _mk_entry(frm, "Pasta saída",            vars["pasta_saida"],           width=80, row=2)
        _mk_entry(frm, "Pasta PDFs",             vars["pastas_pdf"],            width=80, row=3)
        _mk_entry(frm, "Pasta baixados",         vars["pastas_baixados"],       width=80, row=4)

    elif secao == "sequenciais":
        for key in ("nosso_numero","ultima_remessa"):
            vars.setdefault(key, tk.StringVar(value=data.get(key, "")))
        _mk_entry(frm, "Nosso Número atual",  vars["nosso_numero"],  width=20, row=0)
        _mk_entry(frm, "Remessa atual (7d)",  vars["ultima_remessa"],width=12, row=1)

    else:
        ttk.Label(frm, text=f"Seção '{secao}' ainda não tem UI dedicada.").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Use 'Salvar' para gravar pares (chave/valor) simples.").grid(row=1, column=0, sticky="w")
        r = 2
        for k in sorted(data.keys() or []):
            vars.setdefault(k, tk.StringVar(value=data.get(k, "")))
            _mk_entry(frm, k, vars[k], row=r); r += 1

    # botões: lado a lado, logo abaixo dos campos
    btns = ttk.Frame(host)
    btns.pack(anchor="w", padx=12, pady=(0,10))
    def _close():
        if isinstance(container, ttk.Notebook):
            try:
                container.forget(host)
            except Exception:
                pass
        elif isinstance(host, tk.Toplevel):
            host.destroy()

    def _salvar():
        payload = {k: v.get() for k, v in vars.items()}
        _save_cfg(session.get_empresa_id(), secao, payload)
        messagebox.showinfo(title, "Dados salvos com sucesso.")
        _close()

    ttk.Button(btns, text="Salvar", command=_salvar).pack(side="left", padx=(0,6))
    ttk.Button(btns, text="Fechar", command=_close).pack(side="left")
