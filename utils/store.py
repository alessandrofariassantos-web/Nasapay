# utils/store.py  — multi-empresa + migrações idempotentes
import os, sqlite3, hashlib, datetime, json
from typing import Optional, List, Dict, Iterable
import re as _re
import sqlite3, json, re

def _connect(db_path=r"C:\nasapay\nasapay.db") -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con

def _digits(s: str | None, limit: int | None = None) -> str:
    s = re.sub(r"\D", "", s or "")
    return s[:limit] if limit else s

# ========================= util simples =========================
def _only_digits(_s: Optional[str]) -> str:
    return _re.sub(r"\D", "", _s or "")

# ----------------- low level helpers -----------------
def _exec(conn, sql: str, params: Iterable = ()):
    cur = conn.cursor()
    cur.execute(sql, tuple(params))
    return cur

def _fetchall(conn, sql: str, params: Iterable = ()):
    return _exec(conn, sql, params).fetchall()

def _fetchone(conn, sql: str, params: Iterable = ()):
    return _exec(conn, sql, params).fetchone()

# ----------------- schema helpers -----------------
def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return bool(con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (name,)
    ).fetchone())

def _table_info(con: sqlite3.Connection, table: str) -> List[sqlite3.Row]:
    return con.execute(f"PRAGMA table_info({table})").fetchall()

def _has_column(con: sqlite3.Connection, table: str, col: str) -> bool:
    for r in _table_info(con, table):
        cname = r["name"] if isinstance(r, sqlite3.Row) else r[1]
        if cname == col:
            return True
    return False

def _try_add_column(con: sqlite3.Connection, table: str, coldef: str) -> None:
    """
    Tenta: ALTER TABLE <table> ADD COLUMN <coldef>
    coldef ex.: 'fantasia TEXT'
    """
    col = coldef.split()[0]
    if _table_exists(con, table) and not _has_column(con, table, col):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {coldef}")

# ----------------- multi-empresa core -----------------
def ensure_multi_empresa_columns(conn: sqlite3.Connection):
    """
    Garante colunas empresa_id nas tabelas críticas e índices relacionados.
    """
    targets = [
        ("pagador", "empresa_id", "INTEGER"),
        ("titulo", "empresa_id", "INTEGER"),
        ("boleto", "empresa_id", "INTEGER"),
        ("email_log", "empresa_id", "INTEGER"),
        ("email_status", "empresa_id", "INTEGER"),
        ("titulo_email_status", "empresa_id", "INTEGER"),
        ("parametros", "empresa_id", "INTEGER"),
    ]
    for tbl, col, typ in targets:
        try:
            _try_add_column(conn, tbl, f"{col} {typ}")
        except Exception:
            pass

    idxs = [
        ("idx_pagador_emp", "pagador", "empresa_id"),
        ("idx_titulo_emp", "titulo", "empresa_id"),
        ("idx_boleto_emp", "boleto", "empresa_id"),
        ("idx_email_log_emp", "email_log", "empresa_id"),
        ("idx_parametros_emp", "parametros", "empresa_id"),
    ]
    for idx_name, tbl_i, col_i in idxs:
        try:
            _exec(conn, f"CREATE INDEX IF NOT EXISTS {idx_name} ON {tbl_i}({col_i})")
        except Exception:
            pass

def ensure_settings_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key  TEXT PRIMARY KEY,
            json TEXT
        )
    """)

def ensure_parametros_table(conn: sqlite3.Connection):
    """
    parâmetros por empresa no formato (empresa_id, secao, chave, valor)
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parametros(
            id    INTEGER PRIMARY KEY AUTOINCREMENT,
            secao TEXT,
            chave TEXT,
            valor TEXT
        )
    """)
    _try_add_column(conn, "parametros", "empresa_id INTEGER")
    try:
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_parametros_emp ON parametros(empresa_id, secao, chave)")
    except Exception:
        pass

    # Se existir somente 1 empresa ativa, faz backfill automático
    eid = get_single_empresa_id_or_none(conn)
    if eid is not None:
        try:
            conn.execute(
                "UPDATE parametros SET empresa_id=? WHERE empresa_id IS NULL OR empresa_id=''",
                (eid,)
            )
        except Exception:
            pass

# === SEQUENCIAIS POR EMPRESA (NN / REMESSA) ===============================
def _ensure_sequenciais_table(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sequenciais(
            empresa_id     INTEGER PRIMARY KEY,
            nn_atual       INTEGER DEFAULT 0,
            remessa_atual  INTEGER DEFAULT 0
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_seq_emp ON sequenciais(empresa_id)")

def _ensure_seq_row(conn: sqlite3.Connection, empresa_id: int):
    _ensure_sequenciais_table(conn)
    row = conn.execute("SELECT 1 FROM sequenciais WHERE empresa_id=?", (empresa_id,)).fetchone()
    if not row:
        conn.execute(
            "INSERT INTO sequenciais(empresa_id, nn_atual, remessa_atual) VALUES (?,0,0)",
            (empresa_id,)
        )

def peek_nn(conn: sqlite3.Connection, empresa_id: int) -> int:
    _ensure_seq_row(conn, empresa_id)
    v = conn.execute("SELECT nn_atual FROM sequenciais WHERE empresa_id=?", (empresa_id,)).fetchone()
    return int((v[0] if v else 0) or 0)

def peek_remessa(conn: sqlite3.Connection, empresa_id: int) -> int:
    _ensure_seq_row(conn, empresa_id)
    v = conn.execute("SELECT remessa_atual FROM sequenciais WHERE empresa_id=?", (empresa_id,)).fetchone()
    return int((v[0] if v else 0) or 0)

def set_nn(conn: sqlite3.Connection, empresa_id: int, value: int):
    _ensure_seq_row(conn, empresa_id)
    conn.execute("UPDATE sequenciais SET nn_atual=? WHERE empresa_id=?", (int(value), empresa_id))

def set_remessa(conn: sqlite3.Connection, empresa_id: int, value: int):
    _ensure_seq_row(conn, empresa_id)
    conn.execute("UPDATE sequenciais SET remessa_atual=? WHERE empresa_id=?", (int(value), empresa_id))

def next_nn(conn: sqlite3.Connection, empresa_id: int, width: int = 11) -> str:
    cur_val = peek_nn(conn, empresa_id)
    nxt = cur_val + 1
    set_nn(conn, empresa_id, nxt)
    s = str(nxt).zfill(width)
    if len(s) > width:
        raise ValueError(f"Nosso Número ultrapassou {width} dígitos (valor atual={nxt}).")
    return s

def next_remessa(conn: sqlite3.Connection, empresa_id: int, width: int = 6) -> str:
    cur_val = peek_remessa(conn, empresa_id)
    nxt = cur_val + 1
    set_remessa(conn, empresa_id, nxt)
    s = str(nxt).zfill(width)
    if len(s) > width:
        raise ValueError(f"Sequencial de remessa ultrapassou {width} dígitos (valor atual={nxt}).")
    return s

# ----------------- empresas helpers -----------------
def empresas_list(conn: sqlite3.Connection):
    # detecta nome (preferindo 'nome', senão 'razao_social')
    colnames = [r[1] for r in conn.execute("PRAGMA table_info(empresas)").fetchall()]
    name_expr = "nome" if "nome" in colnames else "razao_social"
    rows = _fetchall(conn, f"""
        SELECT id, COALESCE({name_expr}, razao_social) AS nome, cnpj
          FROM empresas
         WHERE ativo IS NULL OR ativo=1
         ORDER BY nome
    """)
    return [{"id": r[0], "nome": r[1] or f"Empresa {r[0]}", "cnpj": r[2]} for r in rows]

def get_single_empresa_id_or_none(conn: sqlite3.Connection) -> Optional[int]:
    rows = conn.execute(
        "SELECT id FROM empresas WHERE ativo IS NULL OR ativo=1 ORDER BY id LIMIT 2"
    ).fetchall()
    if not rows:
        return None
    return rows[0][0] if len(rows) == 1 else None

def backfill_empresa_id(conn: sqlite3.Connection, empresa_id: int):
    target_tables = ["pagador", "titulo", "boleto", "email_log",
                     "email_status", "titulo_email_status", "parametros"]
    for tbl in target_tables:
        try:
            _exec(conn, f"UPDATE {tbl} SET empresa_id=? WHERE empresa_id IS NULL OR empresa_id=''", (empresa_id,))
        except Exception:
            pass

def ensure_company_sequentials(conn: sqlite3.Connection, empresa_id: int):
    _exec(conn, "UPDATE empresas SET nosso_numero_atual=COALESCE(nosso_numero_atual, 1) WHERE id=?", (empresa_id,))
    _exec(conn, "UPDATE empresas SET ultima_remessa=COALESCE(ultima_remessa, 0) WHERE id=?", (empresa_id,))

def next_nosso_numero(conn: sqlite3.Connection, empresa_id: int) -> int:
    conn.execute("BEGIN IMMEDIATE")
    row = _fetchone(conn, "SELECT nosso_numero_atual FROM empresas WHERE id=?", (empresa_id,))
    if not row:
        raise RuntimeError("Empresa não encontrada para NN")
    nn = int(row[0] or 1)
    _exec(conn, "UPDATE empresas SET nosso_numero_atual=? WHERE id=?", (nn + 1, empresa_id))
    return nn

def next_sequencial_remessa(conn: sqlite3.Connection, empresa_id: int) -> int:
    hoje = datetime.datetime.now().strftime("%d%m")
    key = f"seq_remessa_{empresa_id}_{hoje}"
    row = _fetchone(conn, "SELECT json FROM settings WHERE key=?", (key,))
    last = int(json.loads(row[0])["n"]) if row and row[0] else 0
    new = last + 1
    payload = json.dumps({"n": new, "date": hoje})
    if row:
        _exec(conn, "UPDATE settings SET json=? WHERE key=?", (payload, key))
    else:
        _exec(conn, "INSERT INTO settings(key, json) VALUES(?, ?)", (key, payload))
    return new

# --- Sacadores / Avalistas (CRUD básico) ---
def sac_list(conn: sqlite3.Connection, empresa_id: int):
    cur = conn.execute(
        "SELECT id, razao, cnpj FROM sacadores_avalistas WHERE empresa_id=? ORDER BY razao",
        (empresa_id,)
    )
    return [dict(id=r[0], razao=r[1], cnpj=r[2] or "") for r in cur.fetchall()]

def sac_upsert(conn: sqlite3.Connection, empresa_id: int, *, id=None, razao: str, cnpj: str = "") -> int:
    cnpj = _only_digits(cnpj)
    if id:
        conn.execute(
            "UPDATE sacadores_avalistas SET razao=?, cnpj=? WHERE id=? AND empresa_id=?",
            (razao.strip(), cnpj, id, empresa_id)
        )
        return int(id)
    cur = conn.execute(
        "INSERT OR REPLACE INTO sacadores_avalistas (empresa_id, razao, cnpj) VALUES (?,?,?)",
        (empresa_id, razao.strip(), cnpj)
    )
    return int(cur.lastrowid)

def sac_delete(conn: sqlite3.Connection, empresa_id: int, id: int):
    conn.execute("DELETE FROM sacadores_avalistas WHERE empresa_id=? AND id=?", (empresa_id, id))

# ----------------- path / connection -----------------
_DB_PATH = r"C:/nasapay/nasapay.db"

def _ensure_dir(path: str):
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)

def _connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    dbp = db_path or _DB_PATH
    _ensure_dir(dbp)
    con = sqlite3.connect(dbp)
    con.row_factory = sqlite3.Row
    return con

# ----------------- init / migrations -----------------
def init_db(db_path: Optional[str] = None) -> None:
    """Cria tabelas essenciais e garante colunas novas (empresa_id, parametros, etc.)."""
    con = _connect(db_path)
    cur = con.cursor()

    # Empresas (mínimo necessário)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS empresas(
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            razao_social       TEXT,
            nome               TEXT,
            cnpj               TEXT,
            ativo              INTEGER,
            nosso_numero_atual INTEGER,
            ultima_remessa     INTEGER
        )
    """)

    # Base já usada pelo app
    cur.execute("""
        CREATE TABLE IF NOT EXISTS pagador (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc TEXT UNIQUE NOT NULL,
            nome TEXT,
            email TEXT,
            endereco TEXT, cidade TEXT, uf TEXT, cep TEXT, telefone TEXT,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS titulo (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pagador_id INTEGER NOT NULL,
            origem TEXT,
            documento TEXT,
            nosso_numero TEXT,
            nn_dv TEXT,
            carteira TEXT,
            valor_centavos INTEGER DEFAULT 0,
            vencimento TEXT,
            emissao TEXT,
            status TEXT DEFAULT 'gerado',
            created_at TEXT DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (pagador_id) REFERENCES pagador(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_pagador_doc ON pagador(doc)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_titulo_pag ON titulo(pagador_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_titulo_nn  ON titulo(nosso_numero)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_titulo_doc ON titulo(documento)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS boleto (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo_id INTEGER UNIQUE NOT NULL,
            pdf_path TEXT NOT NULL,
            pdf_sha1 TEXT UNIQUE NOT NULL,
            generated_at TEXT DEFAULT (datetime('now','localtime')),
            email_para TEXT,
            email_enviado_em TEXT,
            email_msg_id TEXT,
            FOREIGN KEY (titulo_id) REFERENCES titulo(id)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_boleto_titulo ON boleto(titulo_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_boleto_sha1   ON boleto(pdf_sha1)")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS email_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo_id INTEGER,
            "to" TEXT,
            subject TEXT,
            sent_at TEXT,
            status TEXT,
            error TEXT,
            FOREIGN KEY (titulo_id) REFERENCES titulo(id)
        )
    """)

 # --- Sacadores/Avalistas (por empresa) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sacadores_avalistas(
            empresa_id INTEGER NOT NULL,
            id         INTEGER NOT NULL,
            razao      TEXT,
            cnpj       TEXT,
            PRIMARY KEY (empresa_id, id)
        )
    """)

    # --- Contas Bancárias (por empresa) ---
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contas_bancarias(
            empresa_id  INTEGER NOT NULL,
            id          INTEGER NOT NULL,
            isp         TEXT,
            banco       TEXT,
            agencia     TEXT,
            dv_agencia  TEXT,
            conta       TEXT,
            dv_conta    TEXT,
            carteira    TEXT,
            convenio    TEXT,
            PRIMARY KEY (empresa_id, id)
        )
    """)


    # Auxiliares
    ensure_settings_table(con)
    ensure_parametros_table(con)

    # Migrações simples
    _try_add_column(con, "pagador", "fantasia TEXT")
    _try_add_column(con, "pagador", "contato  TEXT")

    # Multi-empresa
    ensure_multi_empresa_columns(con)

    # Sacadores/Avalistas (multi por empresa)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sacadores_avalistas (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            empresa_id INTEGER NOT NULL,
            razao      TEXT    NOT NULL,
            cnpj       TEXT,
            FOREIGN KEY (empresa_id) REFERENCES empresas(id)
        )
    """)
    # Índices
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sac_avalista_emp ON sacadores_avalistas(empresa_id)")
    # índice único com expressão para tratar cnpj NULL ~ '' (impede duplicidade por empresa/razao/cnpj):
    cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_sac_avalista ON sacadores_avalistas(empresa_id, razao, IFNULL(cnpj,''))")

    # Se houver só 1 empresa ativa, fazer backfill e preparar sequenciais
    eid = get_single_empresa_id_or_none(con)
    if eid:
        backfill_empresa_id(con, eid)
        ensure_company_sequentials(con, eid)

    con.commit()
    con.close()

def ensure_sacador_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS sacadores_avalistas(
            empresa_id INTEGER NOT NULL,
            id         INTEGER NOT NULL,
            razao      TEXT,
            cnpj       TEXT,
            PRIMARY KEY (empresa_id, id)
        )
    """)
    con.commit()

#======== Funções para Sacador/Avalista

def sac_next_id(con, empresa_id: int) -> int:
    r = con.execute("SELECT COALESCE(MAX(id),0) + 1 AS nx FROM sacadores_avalistas WHERE empresa_id=?", (empresa_id,)).fetchone()
    nx = int(r["nx"] or 1)
    if nx > 9999: raise ValueError("Limite de 9999 sacadores por empresa atingido.")
    return nx

def sac_list(con, empresa_id: int):
    return con.execute(
        "SELECT id, razao, cnpj FROM sacadores_avalistas WHERE empresa_id=? ORDER BY id", (empresa_id,)
    ).fetchall()

def sac_get(con, empresa_id: int, sid: int):
    return con.execute(
        "SELECT id, razao, cnpj FROM sacadores_avalistas WHERE empresa_id=? AND id=?", (empresa_id, sid)
    ).fetchone()

def sac_upsert(con, empresa_id: int, *, id: int | None, razao: str, cnpj: str):
    if id is None:
        nid = sac_next_id(con, empresa_id)
        con.execute(
            "INSERT INTO sacadores_avalistas (empresa_id, id, razao, cnpj) VALUES (?,?,?,?)",
            (empresa_id, nid, razao, _digits(cnpj,14))
        )
    else:
        con.execute(
            "UPDATE sacadores_avalistas SET razao=?, cnpj=? WHERE empresa_id=? AND id=?",
            (razao, _digits(cnpj,14), empresa_id, id)
        )
    con.commit()

def sac_delete(con, empresa_id: int, sid: int):
    con.execute("DELETE FROM sacadores_avalistas WHERE empresa_id=? AND id=?", (empresa_id, sid))
    con.commit()


#========Funções para Contas Bancárias

def ensure_conta_bancaria_table(con):
    con.execute("""
        CREATE TABLE IF NOT EXISTS contas_bancarias(
            empresa_id  INTEGER NOT NULL,
            id          INTEGER NOT NULL,
            isp         TEXT,
            banco       TEXT,
            agencia     TEXT,
            dv_agencia  TEXT,
            conta       TEXT,
            dv_conta    TEXT,
            carteira    TEXT,
            convenio    TEXT,
            PRIMARY KEY (empresa_id, id)
        )
    """)
    con.commit()

def cb_next_id(con, empresa_id: int) -> int:
    r = con.execute("SELECT COALESCE(MAX(id),0) + 1 AS nx FROM contas_bancarias WHERE empresa_id=?", (empresa_id,)).fetchone()
    nx = int(r["nx"] or 1)
    if nx > 9999: raise ValueError("Limite de 9999 contas por empresa atingido.")
    return nx

def cb_list(con, empresa_id: int):
    return con.execute(
        "SELECT id, isp, banco, agencia, dv_agencia, conta, dv_conta, carteira, convenio "
        "FROM contas_bancarias WHERE empresa_id=? ORDER BY id", (empresa_id,)
    ).fetchall()

def cb_get(con, empresa_id: int, cid: int):
    return con.execute(
        "SELECT id, isp, banco, agencia, dv_agencia, conta, dv_conta, carteira, convenio "
        "FROM contas_bancarias WHERE empresa_id=? AND id=?", (empresa_id, cid)
    ).fetchone()

def cb_upsert(con, empresa_id: int, *, id: int | None, isp: str, banco: str, agencia: str,
              dv_agencia: str, conta: str, dv_conta: str, carteira: str, convenio: str):
    data = dict(
        isp=_digits(isp,3), banco=(banco or "").upper()[:30],
        agencia=_digits(agencia,4), dv_agencia=_digits(dv_agencia,1),
        conta=_digits(conta,15), dv_conta=_digits(dv_conta,1),
        carteira=_digits(carteira,3), convenio=_digits(convenio,15),
    )
    if id is None:
        nid = cb_next_id(con, empresa_id)
        con.execute("""
            INSERT INTO contas_bancarias
              (empresa_id, id, isp, banco, agencia, dv_agencia, conta, dv_conta, carteira, convenio)
            VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (empresa_id, nid, data["isp"], data["banco"], data["agencia"], data["dv_agencia"],
              data["conta"], data["dv_conta"], data["carteira"], data["convenio"]))
    else:
        con.execute("""
            UPDATE contas_bancarias
               SET isp=?, banco=?, agencia=?, dv_agencia=?, conta=?, dv_conta=?, carteira=?, convenio=?
             WHERE empresa_id=? AND id=?
        """, (data["isp"], data["banco"], data["agencia"], data["dv_agencia"],
              data["conta"], data["dv_conta"], data["carteira"], data["convenio"], empresa_id, id))
    con.commit()

def cb_delete(con, empresa_id: int, cid: int):
    con.execute("DELETE FROM contas_bancarias WHERE empresa_id=? AND id=?", (empresa_id, cid))
    con.commit()


# ---------------------- helpers p/ boletos/títulos ----------------------

def _to_centavos(valor_str: Optional[str]) -> int:
    s = (valor_str or "").strip().replace(" ", "")
    if not s:
        return 0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = float(s)
    except Exception:
        v = float(int(_digits(s) or 0))
    return int(round(max(0.0, v) * 100))

def _sha1_file(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def _today_str() -> str:
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ---------------------- upserts/CRUD -----------------------
def upsert_pagador_from_titulo(t: Dict) -> int:
    doc = _digits(t.get("sacado_cnpj") or t.get("doc_pagador") or "")
    if not doc:
        doc = "00000000000"
    nome = (t.get("sacado") or "").strip()
    email = (t.get("sacado_email") or "").strip()
    endereco = (t.get("sacado_endereco") or "").strip()
    cidade = (t.get("sacado_cidade") or "").strip()
    uf     = (t.get("sacado_uf") or "").strip()[:2]
    cep    = _digits(t.get("sacado_cep") or "")
    telefone = _digits(t.get("sacado_telefone") or "")
    fantasia = (t.get("sacado_fantasia") or "").strip().upper()
    contato  = (t.get("sacado_contato")  or "").strip().upper()

    con = _connect(); cur = con.cursor()
    cur.execute("""
        INSERT INTO pagador (doc, nome, email, endereco, cidade, uf, cep, telefone, fantasia, contato)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc) DO UPDATE SET
            nome=COALESCE(NULLIF(excluded.nome,''), pagador.nome),
            email=COALESCE(NULLIF(excluded.email,''), pagador.email),
            endereco=COALESCE(NULLIF(excluded.endereco,''), pagador.endereco),
            cidade=COALESCE(NULLIF(excluded.cidade,''), pagador.cidade),
            uf=COALESCE(NULLIF(excluded.uf,''), pagador.uf),
            cep=COALESCE(NULLIF(excluded.cep,''), pagador.cep),
            telefone=COALESCE(NULLIF(excluded.telefone,''), pagador.telefone),
            fantasia=COALESCE(NULLIF(excluded.fantasia,''), pagador.fantasia),
            contato=COALESCE(NULLIF(excluded.contato,''), pagador.contato)
    """, (doc, nome, email, endereco, cidade, uf, cep, telefone, fantasia, contato))
    con.commit()
    cur.execute("SELECT id FROM pagador WHERE doc=?", (doc,))
    row = cur.fetchone()
    con.close()
    return int(row["id"])

def ensure_titulo(t: Dict, parametros: Dict) -> int:
    pagador_id = upsert_pagador_from_titulo(t)
    origem = (t.get("origem") or "").strip().lower()
    documento = (t.get("documento") or "").strip()
    nosso_numero = _digits(t.get("nosso_numero") or "")
    carteira = _digits(parametros.get("carteira") or "")
    try:
        from utils.boletos_bmp import dv_nosso_numero_base7
        nn_dv = dv_nosso_numero_base7(carteira.zfill(2), nosso_numero.zfill(11)) if nosso_numero else ""
    except Exception:
        nn_dv = ""
    valor_cent = _to_centavos(t.get("valor"))
    vencimento = (t.get("vencimento") or "").strip()
    emissao    = (t.get("emissao") or "").strip()

    con = _connect(); cur = con.cursor()

    if nosso_numero:
        cur.execute("SELECT id FROM titulo WHERE nosso_numero=? AND pagador_id=?", (nosso_numero, pagador_id))
        r = cur.fetchone()
        if r:
            tid = int(r["id"])
            cur.execute("""
                UPDATE titulo
                   SET documento=COALESCE(NULLIF(?, ''), documento),
                       nn_dv=COALESCE(NULLIF(?, ''), nn_dv),
                       carteira=COALESCE(NULLIF(?, ''), carteira),
                       valor_centavos=?,
                       vencimento=COALESCE(NULLIF(?, ''), vencimento),
                       emissao=COALESCE(NULLIF(?, ''), emissao)
                 WHERE id=?""",
                 (documento, nn_dv, carteira, valor_cent, vencimento, emissao, tid))
            con.commit(); con.close(); return tid

    if documento:
        cur.execute("""SELECT id FROM titulo
                       WHERE pagador_id=? AND documento=?""",
                    (pagador_id, documento))
        r = cur.fetchone()
        if r:
            tid = int(r["id"])
            cur.execute("""
                UPDATE titulo
                   SET nosso_numero=COALESCE(NULLIF(?, ''), nosso_numero),
                       nn_dv=COALESCE(NULLIF(?, ''), nn_dv),
                       carteira=COALESCE(NULLIF(?, ''), carteira),
                       valor_centavos=?,
                       vencimento=COALESCE(NULLIF(?, ''), vencimento),
                       emissao=COALESCE(NULLIF(?, ''), emissao)
                 WHERE id=?""",
                 (nosso_numero, nn_dv, carteira, valor_cent, vencimento, emissao, tid))
            con.commit(); con.close(); return tid

    cur.execute("""
        INSERT INTO titulo (pagador_id, origem, documento, nosso_numero, nn_dv, carteira,
                            valor_centavos, vencimento, emissao, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'gerado')
    """, (pagador_id, origem, documento, nosso_numero, nn_dv, carteira,
          valor_cent, vencimento, emissao))
    con.commit()
    tid = cur.lastrowid
    con.close()
    return int(tid)

def record_boleto(t: Dict, pdf_path: str, parametros: Dict) -> int:
    titulo_id = ensure_titulo(t, parametros)
    sha1 = _sha1_file(pdf_path)

    con = _connect(); cur = con.cursor()
    cur.execute("SELECT id, titulo_id FROM boleto WHERE pdf_sha1=?", (sha1,))
    r = cur.fetchone()
    if r:
        boleto_id = int(r["id"])
        cur.execute("UPDATE boleto SET pdf_path=?, titulo_id=? WHERE id=?",
                    (pdf_path, titulo_id, boleto_id))
        con.commit(); con.close()
        return boleto_id

    cur.execute("SELECT id FROM boleto WHERE titulo_id=?", (titulo_id,))
    r2 = cur.fetchone()
    if r2:
        boleto_id = int(r2["id"])
        cur.execute("UPDATE boleto SET pdf_path=?, pdf_sha1=?, generated_at=? WHERE id=?",
                    (pdf_path, sha1, _today_str(), boleto_id))
        con.commit(); con.close()
        return boleto_id

    cur.execute("""
        INSERT INTO boleto (titulo_id, pdf_path, pdf_sha1)
        VALUES (?, ?, ?)
    """, (titulo_id, pdf_path, sha1))
    con.commit()
    boleto_id = cur.lastrowid
    con.close()
    return int(boleto_id)

# ---------------------- consultas para UI ----------------------
def query_pagadores(q: Optional[str] = None) -> List[Dict]:
    con = _connect(); cur = con.cursor()
    if q:
        like = f"%{q.strip()}%"
        cur.execute("""SELECT id, doc, nome, email, fantasia, contato, telefone, endereco, cidade, uf, cep
                         FROM pagador
                        WHERE doc LIKE ? OR nome LIKE ? OR COALESCE(fantasia,'') LIKE ?
                        ORDER BY nome COLLATE NOCASE""",
                    (like, like, like))
    else:
        cur.execute("""SELECT id, doc, nome, email, fantasia, contato, telefone, endereco, cidade, uf, cep
                         FROM pagador
                        ORDER BY nome COLLATE NOCASE""")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows

def get_pagador_by_doc(doc: str) -> Optional[Dict]:
    con = _connect(); cur = con.cursor()
    cur.execute("SELECT * FROM pagador WHERE doc=?", (_digits(doc),))
    r = cur.fetchone(); con.close()
    return dict(r) if r else None

def query_boletos_por_pagador(pagador_id: int, status: Optional[str] = None,
                              dt_ini: Optional[str] = None, dt_fim: Optional[str] = None) -> List[Dict]:
    con = _connect(); cur = con.cursor()
    where = ["t.pagador_id = ?"]
    args: List = [pagador_id]

    if status == "pendente":
        where.append("b.email_enviado_em IS NULL")
    elif status == "enviado":
        where.append("b.email_enviado_em IS NOT NULL")

    if dt_ini:
        where.append("b.generated_at >= ?"); args.append(dt_ini)
    if dt_fim:
        where.append("b.generated_at <= ?"); args.append(dt_fim)

    sql = f"""
    SELECT b.id as boleto_id, b.titulo_id, b.pdf_path, b.pdf_sha1,
           b.generated_at, b.email_para, b.email_enviado_em, b.email_msg_id,
           t.documento, t.nosso_numero, t.nn_dv, t.carteira,
           t.valor_centavos, t.vencimento, t.emissao
      FROM boleto b
      JOIN titulo t ON t.id = b.titulo_id
     WHERE {' AND '.join(where)}
     ORDER BY b.generated_at DESC
    """
    cur.execute(sql, args)
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows

def set_email_pagador(pagador_id: int, email: str) -> None:
    con = _connect(); cur = con.cursor()
    cur.execute("UPDATE pagador SET email=? WHERE id=?", (email.strip(), pagador_id))
    con.commit(); con.close()

def marcar_boleto_enviado(boleto_id: int, to: str, msg_id: Optional[str]) -> None:
    con = _connect(); cur = con.cursor()
    cur.execute("""
        UPDATE boleto
           SET email_para=?, email_enviado_em=?, email_msg_id=?
         WHERE id=?
    """, (to, _today_str(), msg_id or "", boleto_id))
    con.commit(); con.close()

def log_envio(titulo_id: int, to: str, subject: str, status: str, error: Optional[str]) -> None:
    con = _connect(); cur = con.cursor()
    cur.execute("""
        INSERT INTO email_log (titulo_id, "to", subject, sent_at, status, error)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (titulo_id, to, subject, _today_str(), status, (error or "")))
    con.commit(); con.close()

def debug_counts() -> Dict[str, int]:
    con = _connect(); cur = con.cursor()
    cur.execute("SELECT COUNT(*) AS n FROM pagador"); a = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM titulo");  b = cur.fetchone()["n"]
    cur.execute("SELECT COUNT(*) AS n FROM boleto");  c = cur.fetchone()["n"]
    con.close()
    return {"pagador": a, "titulo": b, "boleto": c}
