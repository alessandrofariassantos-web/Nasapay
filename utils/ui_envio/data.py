# utils/ui_envio/data.py
"""
Camada de dados para a tela de Envio.
- Carrega pagadores e títulos a partir do banco C:\nasapay\nasapay.db
- Faz pequena migração (adiciona colunas faltantes em pagador)
- Persiste edições inline (fantasia/telefone/email/contato)
- Marca envio (atualiza status em memória e retorna timestamp ISO)
"""
import os, sqlite3, datetime, re
from typing import Dict, List, Tuple, Optional

_DB_PATH = r"C:\nasapay\nasapay.db"

# ------------- utils -------------
def _con():
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    con = sqlite3.connect(_DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def _fmt_br_dt(iso: str) -> str:
    try:
        dt = datetime.datetime.fromisoformat(iso[:19])
        return dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return iso

def _digits(s: str) -> str:
    return re.sub(r"\D", "", s or "")

def _fmt_phone(s: str) -> str:
    d = _digits(s)
    if len(d) >= 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:11]}"
    elif len(d) >= 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:10]}"
    elif len(d) >= 8:
        return f"{d[:4]}-{d[4:8]}"
    return d

def _fmt_email(s: str) -> str:
    return (s or "").strip().lower()

def _is_valid_email(s: str) -> bool:
    s = (s or "").strip().lower()
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", s))

# ------------- migração -------------
def _ensure_columns():
    """
    Garante que a tabela pagador tenha as colunas usadas na UI:
      fantasia TEXT, contato TEXT, telefone TEXT, email TEXT
    (telefone e email já existem no seu banco, mantemos; criamos as demais se faltar)
    """
    con = _con(); cur = con.cursor()
    cur.execute("PRAGMA table_info(pagador)")
    cols = {r["name"].lower() for r in cur.fetchall()}
    to_add = []
    if "fantasia" not in cols: to_add.append(("fantasia", "TEXT"))
    if "contato"  not in cols: to_add.append(("contato",  "TEXT"))
    for name, typ in to_add:
        try:
            cur.execute(f"ALTER TABLE pagador ADD COLUMN {name} {typ}")
        except Exception:
            pass
    con.commit(); con.close()

# ------------- carregamento inicial -------------
def load_initial(page) -> None:
    """
    Prepara estruturas internas da página (mapas) e carrega primeira lista de pagadores/títulos.
    """
    _ensure_columns()
    page._map_pags = []        # [{id, razao, fantasia, fone, email, contato}, ...]
    page._map_titles = {}      # pid -> [{tid, doc, venc, valor, nosso, status, first_ts, last_ts}, ...]
    refresh_pagadores(page, "")

# ------------- leitura de dados -------------
def _fetch_pagadores(filtro_nome: str) -> List[Dict]:
    con = _con(); cur = con.cursor()
    if filtro_nome:
        like = f"%{filtro_nome.strip()}%"
        cur.execute("""SELECT id, nome AS razao,
                              COALESCE(fantasia,'') AS fantasia,
                              COALESCE(telefone,'') AS fone,
                              COALESCE(email,'') AS email,
                              COALESCE(contato,'') AS contato
                         FROM pagador
                        WHERE nome LIKE ? OR fantasia LIKE ?
                        ORDER BY nome COLLATE NOCASE""", (like, like))
    else:
        cur.execute("""SELECT id, nome AS razao,
                              COALESCE(fantasia,'') AS fantasia,
                              COALESCE(telefone,'') AS fone,
                              COALESCE(email,'') AS email,
                              COALESCE(contato,'') AS contato
                         FROM pagador
                        ORDER BY nome COLLATE NOCASE""")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows

def _fetch_boletos_do_pagador(pagador_id: int) -> List[Dict]:
    con = _con(); cur = con.cursor()
    cur.execute("""
        SELECT b.id   AS boleto_id,
               t.id   AS titulo_id,
               t.documento AS doc,
               t.vencimento AS venc,
               printf('%.2f', t.valor_centavos/100.0) AS valor,
               t.nosso_numero AS nosso,
               COALESCE(b.email_enviado_em,'') AS sent_ts
          FROM boleto b
          JOIN titulo t ON t.id=b.titulo_id
         WHERE t.pagador_id=?
         ORDER BY t.vencimento, t.documento
    """, (pagador_id,))
    rows = []
    for r in cur.fetchall():
        d = dict(r)
        d["tid"] = int(d.pop("boleto_id"))  # usamos boleto_id como "tid" para marcação de envio
        sent = (d.pop("sent_ts") or "").strip()
        if sent:
            d["first_ts"] = sent
            d["last_ts"]  = sent
            d["send_count"] = 1
            d["status"] = "enviado em " + _fmt_br_dt(sent)
        else:
            d["first_ts"] = ""
            d["last_ts"] = ""
            d["send_count"] = 0
            d["status"] = "não enviado"
        rows.append(d)
    con.close()
    return rows

# ------------- API da tela -------------
def refresh_pagadores(page, filtro_nome: str) -> None:
    """
    Recarrega a lista de pagadores e (preguiçosamente) os títulos de cada um.
    Preenche o Treeview da esquerda.
    """
    page._map_pags = _fetch_pagadores(filtro_nome or "")
    # carrega títulos para cada pagador da lista atual
    page._map_titles = {str(p["id"]): _fetch_boletos_do_pagador(int(p["id"])) for p in page._map_pags}

    tvP = page._tvP
    tvP.delete(*tvP.get_children())
    for p in page._map_pags:
        tvP.insert("", "end", iid=str(p["id"]),
                   values=(p["razao"], p["fantasia"], p["fone"], p["email"], p["contato"]))

def save_pagador_field(page, pagador_id: str, col: str, value: str) -> None:
    """
    Atualiza um campo editável do pagador: fantasia, fone(telefone), email, contato.
    """
    field_map = {"fantasia": "fantasia", "fone": "telefone", "email": "email", "contato": "contato"}
    dbcol = field_map.get(col)
    if not dbcol:
        return
    con = _con(); cur = con.cursor()
    cur.execute(f"UPDATE pagador SET {dbcol}=? WHERE id=?", (value, int(pagador_id)))
    con.commit(); con.close()

def record_send(page, tid_list: List[int]) -> str:
    """
    Marca os boletos (pelo id usado em 'tid') como enviados agora.
    Retorna timestamp ISO usado.
    """
    if not tid_list:
        return datetime.datetime.now().isoformat(timespec="seconds")
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    con = _con(); cur = con.cursor()
    cur.executemany("UPDATE boleto SET email_enviado_em=? WHERE id=?", [(ts, int(x)) for x in tid_list])
    con.commit(); con.close()
    return ts

# reexport util p/ core
__all__ = [
    "_fmt_br_dt", "_fmt_phone", "_fmt_email", "_is_valid_email",
    "load_initial", "refresh_pagadores", "save_pagador_field", "record_send"
]
