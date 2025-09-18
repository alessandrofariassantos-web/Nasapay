# audit_nasapay.py
# Usage:
#   1) Abra o PowerShell
#   2) Set-Location C:\nasapay
#   3) py .\audit_nasapay.py   (ou: python .\audit_nasapay.py)
#
# Saída: nasapay_audit_report.md (resumo do projeto em Markdown)

import sys, csv, json, ast, io, re, sqlite3, datetime
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
REPORT = ROOT / "nasapay_audit_report.md"

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".bmp", ".webp"}
CSV_EXT   = {".csv"}
DB_EXT    = {".db", ".sqlite", ".sqlite3"}
PY_EXT    = {".py", ".pyw"}
JSON_EXT  = {".json",}
OTHER_TEXT_EXT = {".md", ".txt", ".ini", ".cfg", ".yaml", ".yml", ".toml"}

def human_size(n: float) -> str:
    for unit in ["B","KB","MB","GB","TB"]:
        if n < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"

def safe_read_text(path: Path, max_chars: int = 20000) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_chars)
    except Exception as e:
        return f"<<unreadable: {e}>>"

def parse_python(path: Path) -> dict:
    info = {
        "file": str(path),
        "docstring": None,
        "imports": set(),
        "classes": [],
        "functions": [],
        "has_main": False,
    }
    try:
        text = safe_read_text(path, max_chars=200000)
        tree = ast.parse(text)
        info["docstring"] = ast.get_docstring(tree)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        info["imports"].add(n.name.split(".")[0])
                else:
                    if node.module:
                        info["imports"].add(node.module.split(".")[0])
            elif isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                info["classes"].append({"name": node.name, "methods_count": len(methods)})
            elif isinstance(node, ast.FunctionDef):
                info["functions"].append(node.name)
        info["has_main"] = ("if __name__" in text) and ("__main__" in text)
    except Exception as e:
        info["error"] = f"AST parse error: {e}"
    info["imports"] = sorted(info["imports"])
    return info

def summarize_requirements(root: Path):
    reqs = []
    for p in (root/"requirements.txt", root/"requirements-dev.txt"):
        if p.exists():
            try:
                for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#"):
                        reqs.append(line)
            except Exception as e:
                reqs.append(f"<<unable to read {p.name}: {e}>>")
    pyproj = root/"pyproject.toml"
    if pyproj.exists():
        content = safe_read_text(pyproj, max_chars=50000)
        reqs.append("<<pyproject.toml present>>")
        if re.search(r"\[project\.dependencies\]", content):
            reqs.append("<<project.dependencies block detected>>")
    return reqs

def list_sqlite_schema(db_path: Path, limit_tables: int = 20):
    out = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cur = conn.cursor()
        cur.execute("SELECT name, type FROM sqlite_master WHERE type in ('table','view') ORDER BY name")
        rows = cur.fetchall()
        for name, typ in rows[:limit_tables]:
            out.append(f"- {typ}: {name}")
            try:
                cur.execute(f"PRAGMA table_info('{name}')")
                cols = cur.fetchall()
                col_list = ", ".join([c[1] for c in cols])
                out.append(f"  - columns ({len(cols)}): {col_list}")
            except Exception as e:
                out.append(f"  - columns: <error {e}>")
        if len(rows) > limit_tables:
            out.append(f"- ... ({len(rows)-limit_tables} more objects not shown)")
        conn.close()
    except Exception as e:
        out.append(f"<<sqlite read error: {e}>>")
    return out

def detect_frameworks(imports):
    frameworks = []
    hints = {
        "tkinter": "Desktop GUI (Tkinter)",
        "customtkinter": "Desktop GUI (CustomTkinter)",
        "PySimpleGUI": "Desktop GUI (PySimpleGUI)",
        "flask": "Web API/UI (Flask)",
        "fastapi": "Web API (FastAPI)",
        "django": "Web (Django)",
        "flet": "Desktop/Web (Flet)",
        "pandas": "Data processing (pandas)",
        "sqlite3": "SQLite DB",
        "sqlalchemy": "ORM (SQLAlchemy)",
        "requests": "HTTP client (requests)",
        "smtplib": "E-mail (smtplib)",
        "email": "E-mail utils (email)",
        "reportlab": "PDF generation (reportlab)",
        "fpdf": "PDF generation (fpdf)",
        "openpyxl": "Excel (openpyxl)",
        "pywin32": "Windows integration (pywin32)",
        "qrcode": "QR Code generation (qrcode)",
        "zipfile": "ZIP packaging (zipfile)",
    }
    for lib, desc in hints.items():
        if lib in imports:
            frameworks.append(desc)
    return frameworks

def main():
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    py_files, json_files, csv_files, db_files, images, others = [], [], [], [], [], []
    total_size = 0
    for p in ROOT.rglob("*"):
        if p.is_file():
            try:
                total_size += p.stat().st_size
            except Exception:
                pass
            ext = p.suffix.lower()
            if ext in PY_EXT:
                py_files.append(p)
            elif ext in JSON_EXT:
                json_files.append(p)
            elif ext in CSV_EXT:
                csv_files.append(p)
            elif ext in DB_EXT:
                db_files.append(p)
            elif ext in IMAGE_EXT:
                images.append(p)
            else:
                if ext in OTHER_TEXT_EXT:
                    others.append(p)

    py_infos = [parse_python(p) for p in py_files]
    all_imports = set()
    for info in py_infos:
        for m in info.get("imports", []):
            all_imports.add(m)
    framework_hints = detect_frameworks(all_imports)
    reqs = summarize_requirements(ROOT)

    out = io.StringIO()
    out.write("# Nasapay v1 — Auditoria de Pasta\n\n")
    out.write(f"**Pasta analisada:** `{ROOT}`  \n")
    out.write(f"**Data da análise:** {now}\n\n")
    out.write(f"**Arquivos:** {len(py_files)} .py, {len(json_files)} .json, {len(csv_files)} .csv, {len(db_files)} DBs, {len(images)} imagens, total ~ {human_size(total_size)}\n\n")

    entry_points = [Path(i["file"]).name for i in py_infos if i.get("has_main")]
    if entry_points:
        out.write("## Possíveis pontos de entrada (main)\n")
        for ep in entry_points:
            out.write(f"- {ep}\n")
        out.write("\n")

    if framework_hints:
        out.write("## Tecnologias / Pistas detectadas\n")
        for h in sorted(framework_hints):
            out.write(f"- {h}\n")
        out.write("\n")

    if reqs:
        out.write("## Dependências (detecções básicas)\n")
        for r in reqs:
            out.write(f"- {r}\n")
        out.write("\n")

    out.write("## Arquivos Python (resumo)\n")
    for info in sorted(py_infos, key=lambda x: x["file"].lower()):
        fn = Path(info["file"]).relative_to(ROOT)
        out.write(f"### {fn}\n")
        if info.get("error"):
            out.write(f"- Erro ao analisar: {info['error']}\n\n")
            continue
        if info.get("docstring"):
            ds = info["docstring"].strip().splitlines()[0][:160]
            out.write(f"- Docstring: {ds}\n")
        if info.get("imports"):
            imports_preview = ", ".join(info["imports"][:20])
            if len(info["imports"]) > 20:
                imports_preview += " ..."
            out.write(f"- Imports: {imports_preview}\n")
        if info.get("classes"):
            classes_preview = ", ".join([f"{c['name']}({c['methods_count']} métodos)" for c in info["classes"][:10]])
            if classes_preview:
                out.write(f"- Classes: {classes_preview}\n")
        if info.get("functions"):
            funcs_preview = ", ".join(info["functions"][:12])
            if funcs_preview:
                out.write(f"- Funções: {funcs_preview}\n")
        out.write("\n")

    if json_files:
        out.write("## Arquivos JSON (chaves de alto nível)\n")
        for jf in sorted(json_files):
            rel = jf.relative_to(ROOT)
            try:
                with open(jf, "r", encoding="utf-8", errors="ignore") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    keys = ", ".join(list(data.keys())[:20])
                elif isinstance(data, list):
                    keys = f"lista ({len(data)} itens)"
                else:
                    keys = type(data).__name__
                out.write(f"- {rel}: {keys}\n")
            except Exception as e:
                out.write(f"- {rel}: <<não foi possível ler: {e}>>\n")
        out.write("\n")

    if csv_files:
        out.write("## CSV (cabeçalhos)\n")
        for cf in sorted(csv_files):
            rel = cf.relative_to(ROOT)
            try:
                with open(cf, "r", encoding="utf-8", errors="ignore", newline="") as f:
                    reader = csv.reader(f)
                    headers = next(reader, [])
                out.write(f"- {rel}: {', '.join(headers[:30])}\n")
            except Exception as e:
                out.write(f"- {rel}: <<erro ao ler cabeçalho: {e}>>\n")
        out.write("\n")

    if db_files:
        out.write("## Bancos de dados SQLite (esquema)\n")
        for db in sorted(db_files):
            rel = db.relative_to(ROOT)
            out.write(f"### {rel}\n")
            for line in list_sqlite_schema(db):
                out.write(line + "\n")
            out.write("\n")

    if others:
        out.write("## Outros arquivos de texto\n")
        for t in sorted(others):
            out.write(f"- {t.relative_to(ROOT)}\n")
        out.write("\n")

    REPORT.write_text(out.getvalue(), encoding="utf-8")
    print(f"OK: Relatório gerado -> {REPORT}")
    print("Abra o arquivo .md para ver o resumo.")
    print("(Se preferir, envie esse arquivo aqui no chat para eu ler e resumir em linguagem natural.)")

if __name__ == "__main__":
    main()