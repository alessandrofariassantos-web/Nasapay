# utils/parametros.py — UI de Cadastros + API de parâmetros (compat v2.0)
from __future__ import annotations
import os, re, sqlite3
from typing import Dict
import tkinter as tk
from tkinter import ttk, messagebox

from utils import store, session

# ============================================================
# helpers
# ============================================================
_DIGITS = re.compile(r"\D")

def _digits(s: str | None, limit: int | None = None) -> str:
    d = _DIGITS.sub("", s or "")
    return d[:limit] if (limit and limit > 0) else d

def _ensure_param_table(conn: sqlite3.Connection) -> None:
    """
    Tabela de parâmetros K/V por empresa e seção:
    (empresa_id, secao, chave) -> valor
    """
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

def _save_pair(conn: sqlite3.Connection, eid: int, secao: str, chave: str, valor: str) -> None:
    conn.execute(
        """
        INSERT INTO parametros(empresa_id, secao, chave, valor)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(empresa_id, secao, chave) DO UPDATE SET valor=excluded.valor
        """,
        (eid, secao, chave, valor or "")
    )

# ============================================================
# API pública (usada pelos conversores e gerador de remessa)
# ============================================================
def carregar_parametros() -> Dict[str, str]:
    """
    Retorna um dicionário 'achatado' com parâmetros da empresa ativa:
    - Junta todas as seções de 'parametros'
    - Adiciona campos básicos da empresa (razao_social, cnpj etc.)
    """
    eid = session.get_empresa_id()
    if not eid:
        return {}
    con = store._connect()
    try:
        _ensure_param_table(con)
        # K/V por seções
        rows = con.execute("""
            SELECT secao, chave, COALESCE(valor,'') AS valor
              FROM parametros
             WHERE empresa_id = ?
             ORDER BY secao, chave
        """, (eid,)).fetchall()
        cfg: Dict[str, str] = {r["chave"]: r["valor"] for r in rows}

        # Campos básicos da empresa
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
    """
    Persiste chaves relevantes por seção:
      - 'sequenciais': nosso_numero (11 dig), ultima_remessa (7 dig)
      - 'pastas'     : chaves 'pasta_*' e 'pastas_*'
      - Campos básicos de 'empresa' (quando presentes no cfg)
    """
    if not cfg:
        return
    eid = session.get_empresa_id()
    if not eid:
        return
    con = store._connect()
    try:
        _ensure_param_table(con)

        # Campos básicos da empresa (opcional)
        has_empresa = any(k in cfg for k in ("razao_social","cnpj","endereco","cidade","uf","cep","telefone","email"))
        if has_empresa:
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
                   SET razao_social = COALESCE(:razao_social, razao_social),
                       cnpj         = COALESCE(:cnpj, cnpj),
                       endereco     = COALESCE(:endereco, endereco),
                       cidade       = COALESCE(:cidade, cidade),
                       uf           = COALESCE(:uf, uf),
                       cep          = COALESCE(:cep, cep),
                       telefone     = COALESCE(:telefone, telefone),
                       email        = COALESCE(:email, email)
                 WHERE id = ?
            """, {**up, **{"id": eid}})
        # Sequenciais
        if "nosso_numero" in cfg:
            nn = _digits(cfg.get("nosso_numero"), 11).rjust(11, "0")
            _save_pair(con, eid, "sequenciais", "nosso_numero", nn)
        if "ultima_remessa" in cfg:
            ur = _digits(cfg.get("ultima_remessa"), 7).rjust(7, "0")
            _save_pair(con, eid, "sequenciais", "ultima_remessa", ur)

        # Pastas
        for k, v in cfg.items():
            if k.startswith("pasta_") or k.startswith("pastas_"):
                _save_pair(con, eid, "pastas", k, v or "")

        con.commit()
    finally:
        con.close()

def gerar_nosso_numero(cfg: Dict[str, str] | None = None) -> str:
    """
    Lê o 'sequenciais/nosso_numero' atual, incrementa e persiste (11 dígitos).
    Devolve o novo NN como string. Se 'cfg' vier, atualiza cfg['nosso_numero'].
    """
    eid = session.get_empresa_id()
    if not eid:
        return "00000000001"
    con = store._connect()
    try:
        _ensure_param_table(con)
        row = con.execute(
            "SELECT valor FROM parametros WHERE empresa_id=? AND secao='sequenciais' AND chave='nosso_numero'",
            (eid,)
        ).fetchone()
        atual = int(_digits(row["valor"]) or "0") if row else 0
        prox = max(0, atual) + 1
        _save_pair(con, eid, "sequenciais", "nosso_numero", f"{prox:011d}")
        con.commit()
        if isinstance(cfg, dict):
            cfg["nosso_numero"] = f"{prox:011d}"
        return f"{prox:011d}"
    finally:
        con.close()

# ============================================================
# UI DE CADASTROS (Empresa, Pastas, Sequenciais)
# ============================================================
_TITULOS = {
    "empresa":     "Empresa",
    "pastas":      "Pastas Padrão",
    "sequenciais": "Sequenciais (NN/Remessa)",
}

def _load_cfg(empresa_id: int, secao: str) -> dict:
    con = store._connect()
    try:
        if secao == "empresa":
            r = con.execute(
                "SELECT COALESCE(nome, razao_social) AS nome, razao_social, cnpj, endereco, cidade, uf, cep, telefone, email "
                "FROM empresas WHERE id=?", (empresa_id,)
            ).fetchone()
            if not r:
                return {}
            return {
                "razao_social": (r["razao_social"] or r["nome"] or "").strip(),
                "cnpj":        r["cnpj"] or "",
                "endereco":    r["endereco"] or "",
                "cidade":      r["cidade"] or "",
                "uf":          (r["uf"] or "")[:2],
                "cep":         r["cep"] or "",
                "telefone":    r["telefone"] or "",
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
                   SET razao_social = :razao_social,
                       cnpj         = :cnpj,
                       endereco     = :endereco,
                       cidade       = :cidade,
                       uf           = :uf,
                       cep          = :cep,
                       telefone     = :telefone,
                       email        = :email
                 WHERE id = :id
            """, {**up, "id": empresa_id})
            con.commit()
            return

        _ensure_param_table(con)
        for k, v in (data or {}).items():
            _save_pair(con, empresa_id, secao, k, str(v or ""))
        con.commit()
    finally:
        con.close()

def _mk_entry(frm, label, var, width=40, row=None, col=0, padx=(6,6), pady=(4,4)):
    ttk.Label(frm, text=label).grid(row=row, column=col, sticky="w", padx=padx, pady=pady)
    ent = ttk.Entry(frm, textvariable=var, width=width)
    ent.grid(row=row, column=col+1, sticky="we", padx=padx, pady=pady)
    return ent

def abrir_parametros(parent=None, secao: str="empresa", container=None):
    """
    Abre a tela de parâmetros numa aba (se container=Notebook) ou numa Toplevel.
    """
    eid = session.get_empresa_id()
    if not eid:
        messagebox.showwarning("Parâmetros", "Selecione uma empresa antes.", parent=parent)
        return

    title = _TITULOS.get(secao, secao.title())
    data  = _load_cfg(eid, secao)

    # Escolhe onde renderizar
    if isinstance(container, ttk.Notebook):
        page = ttk.Frame(container)
        container.add(page, text=title)
        container.select(page)
        host = page
    else:
        top = tk.Toplevel(parent)
        top.title(title)
        top.minsize(640, 360)
        host = top

    frm = ttk.Frame(host)
    frm.pack(fill="both", expand=True, padx=12, pady=10)
    frm.columnconfigure(1, weight=1)

    vars = {k: tk.StringVar(value=str(v or "")) for k, v in data.items()}

    if secao == "empresa":
        for key in ("razao_social","cnpj","endereco","cidade","uf","cep","telefone","email"):
            vars.setdefault(key, tk.StringVar(value=""))

        _mk_entry(frm, "Razão Social", vars["razao_social"], row=0)
        _mk_entry(frm, "CNPJ",         vars["cnpj"],         row=1)
        _mk_entry(frm, "Endereço",     vars["endereco"],     row=2)
        _mk_entry(frm, "Cidade",       vars["cidade"],       row=3)
        _mk_entry(frm, "UF",           vars["uf"],           row=4, width=6)
        _mk_entry(frm, "CEP",          vars["cep"],          row=5, width=18)
        _mk_entry(frm, "Telefone",     vars["telefone"],     row=6, width=22)
        _mk_entry(frm, "E-mail",       vars["email"],        row=7, width=40)

    elif secao == "pastas":
        for key in ("pasta_importar_remessa","pasta_entrada","pasta_saida","pastas_pdf","pastas_baixados"):
            vars.setdefault(key, tk.StringVar(value=data.get(key, "")))
        _mk_entry(frm, "Pasta importar remessa", vars["pasta_importar_remessa"], row=0)
        _mk_entry(frm, "Pasta entrada (legado)", vars["pasta_entrada"],         row=1)
        _mk_entry(frm, "Pasta saída",            vars["pasta_saida"],           row=2)
        _mk_entry(frm, "Pasta PDFs",             vars["pastas_pdf"],            row=3)
        _mk_entry(frm, "Pasta baixados",         vars["pastas_baixados"],       row=4)

    elif secao == "sequenciais":
        for key in ("nosso_numero","ultima_remessa"):
            vars.setdefault(key, tk.StringVar(value=data.get(key, "")))
        _mk_entry(frm, "Nosso Número atual",  vars["nosso_numero"],  row=0)
        _mk_entry(frm, "Remessa atual (7d)",  vars["ultima_remessa"],row=1)

    else:
        ttk.Label(frm, text=f"Seção '{secao}' ainda não tem UI dedicada.").grid(row=0, column=0, sticky="w")
        ttk.Label(frm, text="Use 'Salvar' para gravar pares (chave/valor) simples.").grid(row=1, column=0, sticky="w")
        # gera entradas auto das chaves existentes
        r = 2
        for k in sorted(data.keys() or []):
            vars.setdefault(k, tk.StringVar(value=data.get(k, "")))
            _mk_entry(frm, k, vars[k], row=r); r += 1

    btns = ttk.Frame(host); btns.pack(fill="x", padx=12, pady=(0,10))
    def _salvar():
        payload = {k: v.get() for k, v in vars.items()}
        _save_cfg(eid, secao, payload)
        # Atualiza também a API flatten (quem chamar carregar_parametros na sequência)
        messagebox.showinfo(title, "Dados salvos com sucesso.")
    ttk.Button(btns, text="Salvar", command=_salvar).pack(side="left")
    ttk.Button(btns, text="Fechar", command=(host.destroy if isinstance(host, tk.Toplevel) else lambda: None)).pack(side="right")
