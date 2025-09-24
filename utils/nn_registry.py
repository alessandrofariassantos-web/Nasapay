# === utils/nn_registry.py ===
import os, csv, re
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Iterable

# Caminho do CSV de registro
REG_PATH = r"C:/nasapay/nn_registry.csv"

# Colunas persistidas
CSV_FIELDS = [
    "documento", "vencimento", "valor_centavos", "doc_pagador", "sacado",
    "nosso_numero", "agencia", "conta", "carteira", "arquivo", "criado_em"
]

# -------------------- utils básicos --------------------
_re_nd = re.compile(r"\D")

def _dig(s: str) -> str:
    return _re_nd.sub("", str(s or ""))

def _doc_norm(s: str) -> str:
    # documento como dígitos (remove DV se vier com separador no fim)
    s = str(s or "").strip()
    m = re.match(r"^\s*(\d{1,30})\s*[-/\.]\s*\d\s*$", s)
    if m:
        return m.group(1)
    return _dig(s)

def _centavos_from_any(valor) -> int:
    """
    Converte valor vindo como:
      - '1.234,56'  -> 123456
      - '1234,56'   -> 123456
      - '1234.56'   -> 123456   (XML com ponto decimal)
      - '123456'    -> 123456   (já em centavos)
    Sem sinal. Inválidos viram 0.
    """
    if valor is None:
        return 0
    s = str(valor).strip()
    if s == "":
        return 0
    if s.isdigit():  # já em centavos
        try: return max(0, int(s))
        except: return 0
    has_c, has_d = ("," in s), ("." in s)
    if has_c and has_d:
        # padrão BR: 1.234,56
        s = s.replace(".", "").replace(",", ".")
    elif has_c:
        # vírgula decimal
        s = s.replace(",", ".")
    else:
        # ponto decimal (XML)
        s = s
    try:
        v = float(s)
    except Exception:
        v = float(int(_dig(s) or 0))
    return int(round(max(0.0, v) * 100))

def _fmt_brl(cents: int) -> str:
    v = max(0, int(cents or 0)) / 100.0
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _basename(p: str) -> str:
    return os.path.basename(p or "").strip()

# -------------------- IO do CSV --------------------
def _ensure_csv():
    os.makedirs(os.path.dirname(REG_PATH) or ".", exist_ok=True)
    if not os.path.exists(REG_PATH):
        with open(REG_PATH, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=CSV_FIELDS, delimiter=";").writeheader()

def _load_rows() -> List[Dict[str, str]]:
    _ensure_csv()
    rows: List[Dict[str, str]] = []
    with open(REG_PATH, "r", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f, delimiter=";"):
            row = {k: (r.get(k) or "") for k in CSV_FIELDS}
            rows.append(row)
    return rows

def _write_rows(rows: List[Dict[str, str]]):
    _ensure_csv()
    with open(REG_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow({k: (r.get(k) or "") for k in CSV_FIELDS})

# -------------------- chave canônica --------------------
def _key_from_titulo(t: dict) -> Tuple[str, str, str, str]:
    doc = _doc_norm(t.get("documento", ""))
    venc = str(t.get("vencimento", "")).strip()
    cents = str(_centavos_from_any(t.get("valor", "0")))
    docpag = _dig(t.get("sacado_cnpj") or t.get("doc_pagador") or "")
    return (doc, venc, cents, docpag)

# -------------------- API pública --------------------
def next_nosso_numero(params: dict) -> str:
    ag = str(params.get("agencia", "")).zfill(4)
    cc = str(params.get("conta", "")).zfill(7)
    cart = str(params.get("carteira", "")).zfill(2)
    maxi = 0
    for r in _load_rows():
        if r.get("agencia") == ag and r.get("conta") == cc and r.get("carteira") == cart:
            nn = _dig(r.get("nosso_numero"))
            if nn:
                try: maxi = max(maxi, int(nn))
                except: pass
    return str(maxi + 1).zfill(11)

def buscar_nosso_numero(titulo: dict) -> Optional[str]:
    k = _key_from_titulo(titulo)
    latest_dt = None
    nn = None
    
    # Debug: mostrar chave procurada
    print(f"[DEBUG] Buscando NN para chave: {k}")
    
    for r in _load_rows():
        rk = (_doc_norm(r["documento"]), r["vencimento"], r["valor_centavos"], _dig(r["doc_pagador"]))
        
        # Debug: mostrar comparação
        if r["documento"] and _doc_norm(r["documento"]) == k[0]:
            print(f"[DEBUG] Comparando:")
            print(f"  Procurado: {k}")
            print(f"  Registro:  {rk}")
            print(f"  Match: {rk == k}")
        
        if rk == k and r.get("nosso_numero"):
            try:
                dt = datetime.fromisoformat((r.get("criado_em") or "").replace(" ", "T"))
            except Exception:
                dt = None
            if latest_dt is None or (dt and dt > latest_dt):
                latest_dt = dt
                nn = r["nosso_numero"]
                print(f"[DEBUG] NN encontrado: {nn}")
    
    if not nn:
        print(f"[DEBUG] Nenhum NN encontrado para {k}")
    
    return nn

def registrar_titulos(titulos: List[dict], params: dict, meta: dict | None = None):
    """
    Grava/atualiza CSV com (doc, venc, valor_centavos, doc_pagador) como chave.
    - meta['arquivo'] opcional
    - meta['override_nn'] True para forçar atualização do NN/arquivo/sacado
    """
    rows = _load_rows()
    index = {(_doc_norm(r["documento"]), r["vencimento"], r["valor_centavos"], _dig(r["doc_pagador"])): i
             for i, r in enumerate(rows)}

    ag = str(params.get("agencia", "")).zfill(4)
    cc = str(params.get("conta", "")).zfill(7)
    cart = str(params.get("carteira", "")).zfill(2)
    override = bool((meta or {}).get("override_nn"))
    arquivo = (meta or {}).get("arquivo", "") or ""

    changed = False
    for t in titulos:
        doc, venc, cents, docp = _key_from_titulo(t)
        nn = str(_dig(t.get("nosso_numero"))).zfill(11) if t.get("nosso_numero") else ""
        sacado = str(t.get("sacado") or "").strip()

        key = (doc, venc, cents, docp)
        i = index.get(key)
        if i is None:
            rows.append({
                "documento": doc, "vencimento": venc, "valor_centavos": cents,
                "doc_pagador": docp, "sacado": sacado,
                "nosso_numero": nn, "agencia": ag, "conta": cc, "carteira": cart,
                "arquivo": arquivo, "criado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
            index[key] = len(rows) - 1
            changed = True
        elif override:
            r = rows[i]
            if nn: r["nosso_numero"] = nn
            if sacado: r["sacado"] = sacado
            if arquivo: r["arquivo"] = arquivo
            r["criado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            changed = True

    if changed:
        _write_rows(rows)

def list_entries(filtro: Optional[str] = None, sort_by: str = "timestamp", reverse: bool = True) -> List[Dict[str, str]]:
    rows = _load_rows()
    out: List[Dict[str, str]] = []
    for i, r in enumerate(rows):
        cents = r.get("valor_centavos") or "0"
        try:
            cents_i = int(cents) if str(cents).isdigit() else _centavos_from_any(cents)
        except Exception:
            cents_i = 0
        out.append({
            "key": str(i),
            "sacado": (r.get("sacado") or r.get("doc_pagador") or "").strip(),
            "documento": r.get("documento", ""),
            "valor": _fmt_brl(cents_i),
            "vencimento": r.get("vencimento", ""),
            "nosso_numero": r.get("nosso_numero", ""),
            "arquivo": r.get("arquivo", ""),
            "arquivo_nome": _basename(r.get("arquivo", "")),
            "timestamp": r.get("criado_em", ""),
            "_valor_centavos": str(max(0, cents_i)),
            "doc_pagador": r.get("doc_pagador", ""),
            "agencia": r.get("agencia", ""),
            "conta": r.get("conta", ""),
            "carteira": r.get("carteira", ""),
        })

    if filtro:
        f = filtro.strip().lower()
        if f:
            def ok(d):
                return any((d.get(c, "").lower().find(f) >= 0) for c in
                           ["sacado", "documento", "nosso_numero", "arquivo_nome", "valor", "timestamp"])
            out = [d for d in out if ok(d)]

    if sort_by not in ("sacado", "documento", "vencimento", "valor", "nosso_numero", "arquivo_nome", "timestamp"):
        sort_by = "timestamp"
    out.sort(key=lambda d: d.get(sort_by, ""), reverse=reverse)
    return out

def search_entries(filtro: Optional[str] = None, sort_by: str = "criado_em", reverse: bool = True) -> List[Dict[str, str]]:
    return list_entries(filtro=filtro, sort_by=("timestamp" if sort_by == "criado_em" else sort_by), reverse=reverse)

def update_entry(row_id, nosso_numero: Optional[str] = None, arquivo: Optional[str] = None, sacado: Optional[str] = None) -> bool:
    try:
        idx = int(row_id)
    except Exception:
        return False
    rows = _load_rows()
    if not (0 <= idx < len(rows)): return False
    ch = False
    if nosso_numero is not None:
        nn = _dig(nosso_numero).zfill(11)
        if len(nn) != 11:
            raise ValueError("Nosso Número deve ter 11 dígitos.")
        if rows[idx].get("nosso_numero") != nn:
            rows[idx]["nosso_numero"] = nn; ch = True
    if arquivo is not None:
        arq = (arquivo or "").strip()
        if rows[idx].get("arquivo") != arq:
            rows[idx]["arquivo"] = arq; ch = True
    if sacado is not None:
        sc = (sacado or "").strip()
        if rows[idx].get("sacado", "") != sc:
            rows[idx]["sacado"] = sc; ch = True
    if ch: _write_rows(rows)
    return ch

def delete_entries(ids: Iterable[int | str]) -> int:
    s = set()
    for x in ids:
        try: s.add(int(x))
        except: pass
    if not s: return 0
    rows = _load_rows()
    new = []; rm = 0
    for i, r in enumerate(rows):
        if i in s: rm += 1
        else: new.append(r)
    if rm: _write_rows(new)
    return rm

def import_from_csv(path: str):
    added = updated = skipped = 0
    if not path or not os.path.exists(path): return (0,0,0)

    rows = _load_rows()
    index = {(_doc_norm(r["documento"]), r["vencimento"], r["valor_centavos"], _dig(r["doc_pagador"])): i
             for i, r in enumerate(rows)}

    # detecta delimitador
    delim = ";"
    with open(path, "r", encoding="utf-8", newline="") as f:
        s = f.read(4096)
        if s.count(",") > s.count(";"):
            delim = ","

    with open(path, "r", encoding="utf-8", newline="") as f:
        rdr = csv.DictReader(f, delimiter=delim)
        for raw in rdr:
            doc  = _doc_norm(raw.get("documento") or raw.get("Documento") or "")
            venc = str(raw.get("vencimento") or raw.get("Vencimento") or "").strip()
            valc = raw.get("valor_centavos") or raw.get("ValorCentavos")
            cents = _centavos_from_any(valc if valc not in (None, "") else (raw.get("valor") or raw.get("Valor") or "0"))
            docp = _dig(raw.get("doc_pagador") or raw.get("DocPagador") or raw.get("CPF_CNPJ") or "")
            sac  = (raw.get("sacado") or raw.get("Sacado") or raw.get("Nome") or "").strip()
            nn   = _dig(raw.get("nosso_numero") or raw.get("NossoNumero") or "")
            ag   = _dig(raw.get("agencia") or "")
            cc   = _dig(raw.get("conta") or "")
            cart = _dig(raw.get("carteira") or "")
            arq  = (raw.get("arquivo") or raw.get("Arquivo") or "").strip()
            cri  = (raw.get("criado_em") or raw.get("CriadoEm") or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

            k = (doc, venc, str(cents), docp)
            i = index.get(k)
            if i is None:
                rows.append({
                    "documento": doc, "vencimento": venc, "valor_centavos": str(cents),
                    "doc_pagador": docp, "sacado": sac, "nosso_numero": nn.zfill(11) if nn else "",
                    "agencia": ag, "conta": cc, "carteira": cart, "arquivo": arq, "criado_em": cri
                })
                index[k] = len(rows) - 1
                added += 1
            else:
                ch = False
                if nn and rows[i].get("nosso_numero") != nn:
                    rows[i]["nosso_numero"] = nn; ch = True
                if sac and rows[i].get("sacado", "") != sac:
                    rows[i]["sacado"] = sac; ch = True
                if ch: updated += 1
                else: skipped += 1

    if added or updated: _write_rows(rows)
    return (added, updated, skipped)

def export_to_csv(path: str, filtro: Optional[str] = None) -> int:
    data = list_entries(filtro=filtro, reverse=False)
    if not path: return 0
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, delimiter=";")
        w.writeheader()
        for r in data:
            w.writerow({
                "documento": _doc_norm(r.get("documento","")),
                "vencimento": r.get("vencimento",""),
                "valor_centavos": r.get("_valor_centavos","0"),
                "doc_pagador": r.get("doc_pagador",""),
                "sacado": r.get("sacado",""),
                "nosso_numero": r.get("nosso_numero",""),
                "agencia": r.get("agencia",""),
                "conta": r.get("conta",""),
                "carteira": r.get("carteira",""),
                "arquivo": r.get("arquivo",""),
                "criado_em": r.get("timestamp",""),
            })
    return len(data)

# ---- aliases de compatibilidade (se algum código antigo chamar) ----
def search_entries_wrapper(*a, **k): return search_entries(*a, **k)
def list_mappings(*a, **k):         return list_entries(*a, **k)
def search_mappings(*a, **k):       return search_entries(*a, **k)
def delete_mapping(ids):            return delete_entries(ids)
def import_csv(path):               return import_from_csv(path)
def export_csv(path, rows=None):
    if rows is None:
        return export_to_csv(path, filtro=None)
    # fallback simples
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, delimiter=";")
        w.writeheader()
        for r in rows:
            w.writerow({
                "documento": _doc_norm(r.get("documento","")),
                "vencimento": r.get("vencimento",""),
                "valor_centavos": _dig(r.get("valor","0")),
                "doc_pagador": r.get("doc_pagador",""),
                "sacado": r.get("sacado",""),
                "nosso_numero": r.get("nosso_numero",""),
                "agencia": r.get("agencia",""),
                "conta": r.get("conta",""),
                "carteira": r.get("carteira",""),
                "arquivo": r.get("arquivo",""),
                "criado_em": r.get("timestamp",""),
            })
    return len(rows)
