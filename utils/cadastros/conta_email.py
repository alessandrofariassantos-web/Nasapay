# utils/cadastros/conta_email.py
import tkinter as tk
from tkinter import ttk, messagebox
import re, smtplib, socket, ssl, subprocess
from email.message import EmailMessage
from email.utils import formataddr

from utils.ui_busy import run_with_busy, BusyOverlay  # animação

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# --------- Presets conhecidos ----------
PRESETS = [
    ("Microsoft 365 (Outlook/Exchange Online)", "smtp.office365.com", 587, "TLS",
     "No Microsoft 365 pode ser necessário habilitar 'Authenticated SMTP' e/ou usar SENHA DE APP."),
    ("Outlook.com / Hotmail / Live",            "smtp-mail.outlook.com", 587, "TLS",
     "Em algumas contas, SENHA DE APP é necessária."),
    ("Gmail / Google Workspace",                "smtp.gmail.com", 587, "TLS",
     "Gmail exige SENHA DE APP (com 2FA)."),
    ("Yahoo Mail",                              "smtp.mail.yahoo.com", 465, "SSL",
     "Yahoo normalmente requer SENHA DE APP."),
    ("iCloud Mail (Apple)",                     "smtp.mail.me.com", 587, "TLS",
     "iCloud requer SENHA DE APP (com 2FA)."),
    ("Zoho Mail",                               "smtp.zoho.com", 587, "TLS", ""),
    ("UOL",                                     "smtp.uol.com.br", 587, "TLS", ""),
    ("Terra",                                   "smtp.terra.com.br", 587, "TLS", ""),
    ("BOL",                                     "smtp.bol.com.br", 587, "TLS", ""),
    ("Locaweb",                                 "email-ssl.com.br", 587, "TLS",
     "Pode usar 465/SSL também."),
    ("KingHost",                                "smtp.kinghost.net", 587, "TLS", ""),
]

# ---------- util layout ----------
def _digits(s, limit): return re.sub(r"\D", "", s or "")[:limit]

def _bind_lower(entry: ttk.Entry, var: tk.StringVar):
    guard = {"on": False}
    def on_key(_=None):
        if guard["on"]: return
        guard["on"] = True
        try:
            s = var.get(); idx = entry.index("insert")
            new = (s or "").lower()
            if s != new:
                var.set(new); entry.icursor(min(idx, len(new)))
        finally:
            guard["on"] = False
    entry.bind("<KeyRelease>", on_key)

def _bind_digits(entry: ttk.Entry, var: tk.StringVar, limit: int):
    guard = {"on": False}
    def on_key(_=None):
        if guard["on"]: return
        guard["on"] = True
        try:
            s = var.get(); idx = entry.index("insert")
            raw = re.sub(r"\D","", s or "")[:limit]
            if s != raw:
                var.set(raw); entry.icursor(min(idx, len(raw)))
        finally:
            guard["on"] = False
    entry.bind("<KeyRelease>", on_key)

def _linha(frm, r, label, var, width=40):
    ttk.Label(frm, text=label, width=24, anchor="e").grid(row=r, column=0, padx=6, pady=4, sticky="e")
    e = ttk.Entry(frm, textvariable=var, width=width)
    e.grid(row=r, column=1, padx=6, pady=4, sticky="w")
    return e

# ---------- DNS / MX ----------
def _nslookup_mx(domain: str, timeout: int = 6) -> list[str]:
    try:
        import dns.resolver  # type: ignore
        ans = dns.resolver.resolve(domain, "MX", lifetime=timeout)
        return [str(r.exchange).rstrip(".").lower() for r in ans]
    except Exception:
        pass
    try:
        proc = subprocess.run(["nslookup", "-type=mx", domain], capture_output=True, text=True, timeout=timeout)
        out = (proc.stdout or "") + (proc.stderr or "")
        hosts = []
        for ln in out.splitlines():
            if "mail exchanger" in ln and "=" in ln:
                host = ln.split("=")[-1].strip().rstrip(".").lower()
                if host and host not in hosts: hosts.append(host)
        return hosts
    except Exception:
        return []

def _detect_provider_by_mx(domain: str) -> dict:
    mx = _nslookup_mx(domain)
    s = " ".join(mx)
    if ".protection.outlook.com" in s or "outlook.com" in s:
        return {"host":"smtp.office365.com","porta":587,"seg":"TLS","provedor":"Microsoft 365","mx":mx}
    if "aspmx.l.google.com" in s or ".google.com" in s or "googlemail.com" in s:
        return {"host":"smtp.gmail.com","porta":587,"seg":"TLS","provedor":"Google (Gmail/Workspace)","mx":mx}
    if "mx.zoho.com" in s or "zoho" in s:
        return {"host":"smtp.zoho.com","porta":587,"seg":"TLS","provedor":"Zoho","mx":mx}
    return {"host":f"smtp.{domain}","porta":587,"seg":"TLS","provedor":"Domínio próprio (genérico)","mx":mx}

# ---------- mensagens de erro mais claras (inclui Gmail) ----------
def _friendly_smtp_error(err: Exception, context_host: str) -> tuple[str, str]:
    if isinstance(err, socket.gaierror):
        return ("Servidor SMTP",
                "Não foi possível localizar o servidor informado (DNS).\n\n"
                f"Servidor: {context_host}\n"
                "Verifique o nome do servidor e sua conexão/Firewall.")
    raw = ""; code = ""
    if isinstance(err, smtplib.SMTPAuthenticationError):
        code = str(getattr(err, 'smtp_code', "")) or ""
        raw_bytes = getattr(err, 'smtp_error', b"") or b""
        raw = (raw_bytes.decode(errors="ignore") if isinstance(raw_bytes, (bytes, bytearray)) else str(raw_bytes)) or ""
    else:
        raw = str(err) or ""
    txt = f"{code} {raw}".lower()

    # Gmail / Workspace — senha de app
    if "smtp.gmail.com" in (context_host or "").lower() or "gmail" in txt or "google" in txt:
        if "application-specific password" in txt or "app password" in txt or "5.7.8" in txt or "5.7.14" in txt or "535" in txt:
            return ("Autenticação Gmail",
                    "O Gmail não aceita a senha normal no SMTP.\n"
                    "Ative a Verificação em 2 etapas e use uma SENHA DE APP nesta tela.\n"
                    "Servidor: smtp.gmail.com | Porta: 587 (TLS) ou 465 (SSL) | Usuário: seu e-mail completo.")

    # Microsoft 365 — SMTP AUTH desabilitado
    if "smtpclientauthentication is disabled" in txt or "5.7.139" in txt:
        return ("Autenticação SMTP — Microsoft 365",
                "Falha na autenticação: o SMTP AUTH está DESABILITADO no Microsoft 365.\n\n"
                "Habilite 'Authenticated SMTP' para a caixa e, se houver MFA, use SENHA DE APP.")

    if "authentication unsuccessful" in txt or "5.7.57" in txt or "535" in txt:
        return ("Autenticação SMTP",
                "Falha na autenticação SMTP.\n"
                "Verifique usuário/senha (alguns provedores exigem SENHA DE APP) e a segurança/porta.")

    if "must issue a starttls" in txt or "530 5.7.0" in txt:
        return ("Segurança TLS", "O servidor exige STARTTLS. Selecione Segurança=TLS e porta 587.")

    if "connection unexpectedly closed" in txt or "timed out" in txt:
        return ("Conexão SMTP", "Conexão encerrada/expirada. Verifique host, porta, internet e firewall.")

    return ("SMTP", f"Erro ao enviar e-mail de teste:\n\n{err}")

# ---------- UI ----------
def build_aba_email(nb, state):
    frm = ttk.Frame(nb)
    frm.columnconfigure(1, weight=1)

    # Linha 0 — título
    ttk.Label(frm, text="Conta E-mail", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", padx=6, pady=(6,2))

    # Linha 1 — botão Ajuda/Presets (mais largo)
    def _aplicar_preset(host, porta, seg, hint=None):
        state.var("smtp_host").set(host)
        state.var("smtp_porta").set(str(porta))
        state.var("smtp_tls_ssl").set(seg)
        if not state.var("smtp_usuario").get():
            state.var("smtp_usuario").set((state.var("smtp_email").get() or "").strip().lower())
        txt = f"Servidor: {host}\nPorta: {porta}\nSegurança: {seg}"
        if hint: txt += f"\n\n{hint}"
        messagebox.showinfo("Preset aplicado", txt, parent=frm.winfo_toplevel())

    def _menu_presets(btn):
        m = tk.Menu(btn, tearoff=False)
        for nome, host, porta, seg, obs in PRESETS:
            m.add_command(label=nome, command=lambda h=host,p=porta,s=seg,o=obs: _aplicar_preset(h,p,s,o))
        m.add_separator()
        m.add_command(label="Seu domínio (detectar automaticamente via MX)", command=lambda: _preset_seu_dominio(frm, state))
        m.add_command(label="Seu domínio (smtp.<domínio>)", command=lambda: _preset_generico(frm, state))
        return m

    btn_preset = ttk.Menubutton(frm, text="Ajuda / Presets", width=24)
    btn_preset["menu"] = _menu_presets(btn_preset)
    btn_preset.grid(row=1, column=0, columnspan=2, sticky="w", padx=6, pady=(0,8))

    # Campos principais
    v_from_name = state.var("smtp_nome_remetente")
    _linha(frm, 2, "Nome do Remetente", v_from_name, width=44)

    v_email = state.var("smtp_email")
    e_email = _linha(frm, 3, "E-mail Remetente", v_email); _bind_lower(e_email, v_email)

    v_host = state.var("smtp_host"); _linha(frm, 4, "Servidor SMTP", v_host, width=32)
    v_port = state.var("smtp_porta"); e_port = _linha(frm, 5, "Porta", v_port, width=8); _bind_digits(e_port, v_port, 5)
    v_user = state.var("smtp_usuario"); _linha(frm, 6, "Usuário", v_user, width=32)

    v_pass = state.var("smtp_senha")
    e_pass = _linha(frm, 7, "Senha", v_pass, width=32); e_pass.configure(show="*")
    show_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(frm, text="Mostrar senha", variable=show_var,
                    command=lambda: e_pass.configure(show="" if show_var.get() else "*")).grid(row=7, column=2, padx=6, pady=4, sticky="w")

    v_sec = state.var("smtp_tls_ssl")
    ttk.Label(frm, text="Segurança", width=24, anchor="e").grid(row=8, column=0, padx=6, pady=4, sticky="e")
    ttk.Combobox(frm, textvariable=v_sec, values=["TLS", "SSL", "Nenhum"], state="readonly", width=12)\
        .grid(row=8, column=1, padx=6, pady=4, sticky="w")

    v_auth = tk.BooleanVar(value=bool(state.cfg.get("smtp_requer_auth", True)))
    state._vars["smtp_requer_auth"] = v_auth
    ttk.Checkbutton(frm, text="Servidor requer autenticação", variable=v_auth)\
       .grid(row=9, column=1, sticky="w", padx=6, pady=4)

    # Preencher por domínio conhecido
    def _on_email_blur(_=None):
        s = (v_email.get() or "").strip().lower()
        if not s or "@" not in s: return
        dom = s.split("@",1)[1]
        for nome, host, porta, seg, _ in PRESETS:
            if dom in host or dom in nome.lower():
                if not v_host.get(): v_host.set(host)
                if not v_port.get(): v_port.set(str(porta))
                if not v_sec.get():  v_sec.set(seg)
                break
        if not state.var("smtp_usuario").get(): state.var("smtp_usuario").set(s)
    e_email.bind("<FocusOut>", _on_email_blur)

    # Separador
    ttk.Separator(frm, orient="horizontal").grid(row=10, column=0, columnspan=3, sticky="ew", padx=6, pady=(10,6))

    # Texto orientação + Passos
    ttk.Label(frm, text="Faça um teste dos parâmetros configurados para confirmar que está tudo pronto.",
              foreground="#444").grid(row=11, column=0, columnspan=3, sticky="w", padx=6, pady=(0,8))

    # Passo 1 — label + botão colado
    ttk.Label(frm, text="1º passo - Verificação das Portas de Envio").grid(row=12, column=0, sticky="w", padx=6, pady=(0,4))
    ttk.Button(frm, text="Testar Portas", command=lambda: _testar_portas_async(frm, v_host, v_port, v_sec))\
        .grid(row=12, column=1, sticky="w", padx=6, pady=(0,4))

    # Passo 2 — label + botão colado
    ttk.Label(frm, text="2º passo - Verificação do Usuário e Senha").grid(row=13, column=0, sticky="w", padx=6, pady=(2,6))
    ttk.Button(frm, text="Enviar E-mail de Teste",
               command=lambda: _enviar_teste_async(frm, state, v_from_name, v_email, v_host, v_port, v_user, v_pass, v_sec, v_auth))\
        .grid(row=13, column=1, sticky="w", padx=6, pady=(2,6))

    # Validação simples
    def _validar(_=None):
        s = (v_email.get() or "").strip().lower()
        if s and not EMAIL_RE.match(s):
            messagebox.showwarning("E-mail", "Formato de e-mail aparentemente inválido.", parent=frm.winfo_toplevel())
    e_email.bind("<FocusOut>", _validar)

    return frm

# ---------- Presets “Seu domínio” ----------
def _preset_generico(parent, state):
    email = (state.var("smtp_email").get() or "").strip().lower()
    if "@" not in email:
        messagebox.showinfo("Seu domínio", "Informe primeiro o e-mail remetente.", parent=parent.winfo_toplevel()); return
    dom = email.split("@",1)[1]
    state.var("smtp_host").set(f"smtp.{dom}")
    state.var("smtp_porta").set("587")
    state.var("smtp_tls_ssl").set("TLS")
    if not state.var("smtp_usuario").get():
        state.var("smtp_usuario").set(email)
    messagebox.showinfo("Preset aplicado", f"Servidor: smtp.{dom}\nPorta: 587\nSegurança: TLS", parent=parent.winfo_toplevel())

def _preset_seu_dominio(parent, state):
    email = (state.var("smtp_email").get() or "").strip().lower()
    if "@" not in email:
        messagebox.showinfo("Seu domínio", "Informe primeiro o e-mail remetente para detectarmos pelo domínio.",
                            parent=parent.winfo_toplevel()); return
    dom = email.split("@",1)[1]

    def work():
        return _detect_provider_by_mx(dom)

    def done(res, err):
        if err or not res:
            messagebox.showwarning("Seu domínio", "Não foi possível detectar o provedor via MX.\n"
                                 "Aplicando configuração genérica (smtp.<domínio>, 587/TLS).",
                                 parent=parent.winfo_toplevel())
            _preset_generico(parent, state); return
        state.var("smtp_host").set(res["host"])
        state.var("smtp_porta").set(str(res["porta"]))
        state.var("smtp_tls_ssl").set(res["seg"])
        if not state.var("smtp_usuario").get():
            state.var("smtp_usuario").set((state.var("smtp_email").get() or "").strip().lower())
        obs = ""
        if "Microsoft 365" in res.get("provedor",""):
            obs = "\n\nObservação: pode ser necessário habilitar 'Authenticated SMTP' e/ou usar SENHA DE APP."
        if "Google" in res.get("provedor",""):
            obs = "\n\nObservação: o Gmail exige SENHA DE APP (com 2FA)."
        messagebox.showinfo("Detecção concluída",
                            f"Provedor detectado: {res.get('provedor')}\nMX: {', '.join(res.get('mx') or [])}{obs}",
                            parent=parent.winfo_toplevel())

    run_with_busy(parent, "Consultando DNS do seu domínio…", work, done)

# ---------- Testar Portas (assíncrono com animação) ----------
def _testar_portas_async(frm, v_host, v_port, v_sec):
    host = (v_host.get() or "").strip()
    if not host:
        messagebox.showwarning("Teste de portas", "Informe o Servidor SMTP.", parent=frm.winfo_toplevel()); return

    def work():
        # resolve DNS
        ips = [sa[0] for *_x, sa in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)]
        ips = sorted(set(ips))
        def probe(porta, use_ssl):
            try:
                if use_ssl:
                    ctx = ssl.create_default_context()
                    with smtplib.SMTP_SSL(host, porta, timeout=8, context=ctx) as s:
                        s.noop()
                else:
                    with smtplib.SMTP(host, porta, timeout=8) as s:
                        s.ehlo(); s.starttls(context=ssl.create_default_context()); s.ehlo()
                return "OK (conectou)"
            except Exception as e:
                return f"Falha ({e.__class__.__name__})"
        r587 = probe(587, False)
        r465 = probe(465, True)
        return {"ips":ips, "r587":r587, "r465":r465}

    def done(res, err):
        if err:
            if isinstance(err, socket.gaierror):
                messagebox.showerror("Teste de portas", "Não foi possível resolver o nome do servidor (DNS).",
                                     parent=frm.winfo_toplevel())
            else:
                messagebox.showerror("Teste de portas", f"Erro: {err}", parent=frm.winfo_toplevel())
            return
        msgs = [f"Servidor: {host}", f"IPs: {', '.join(res['ips'])}", "", f"587/TLS: {res['r587']}", f"465/SSL: {res['r465']}"]
        chosen = None
        if "OK" in res["r587"]: chosen = ("587","TLS")
        elif "OK" in res["r465"]: chosen = ("465","SSL")
        if chosen:
            v_port.set(chosen[0]); v_sec.set(chosen[1])
            messagebox.showinfo("Teste de portas", "\n".join(msgs), parent=frm.winfo_toplevel())
        else:
            messagebox.showerror("Teste de portas",
                                 "Não foi possível conectar nas portas testadas (587/TLS e 465/SSL).\n\n" + "\n".join(msgs),
                                 parent=frm.winfo_toplevel())

    run_with_busy(frm, "Testando portas…", work, done)

# ---------- Enviar e-mail de teste (assíncrono com animação) ----------
def _enviar_teste_async(frm, state, v_from_name, v_email, v_host, v_port, v_user, v_pass, v_sec, v_auth):
    if not _valid_email(v_email.get(), frm): return

    host = (v_host.get() or "").strip()
    try: port = int((v_port.get() or "0").strip() or 0)
    except: port = 0
    if not host or not port:
        messagebox.showwarning("SMTP", "Informe Servidor e Porta.", parent=frm.winfo_toplevel()); return

    use_auth = bool(v_auth.get())
    user = (v_user.get() or "").strip() or (v_email.get() or "").strip()
    pwd  = (v_pass.get() or "")
    sec  = (v_sec.get() or "TLS").upper()
    sender_email = (v_email.get() or "").strip()
    sender_name  = (v_from_name.get() or "").strip()
    to_email     = sender_email  # SEM CAMPO: envia para o próprio remetente

    # prepara mensagem aqui (fora da thread — só dados)
    def work():
        msg = EmailMessage()
        msg["From"] = formataddr((sender_name or sender_email, sender_email))
        msg["To"] = to_email
        msg["Subject"] = "Teste de SMTP - Nasapay"
        msg.set_content("E-mail de teste enviado pela tela de Cadastro > Conta E-mail (Nasapay).")
        if sec == "SSL":
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=15) as s:
                s.ehlo()
                if use_auth: s.login(user, pwd)
                s.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=15) as s:
                s.ehlo()
                if sec == "TLS":
                    ctx = ssl.create_default_context()
                    s.starttls(context=ctx); s.ehlo()
                if use_auth: s.login(user, pwd)
                s.send_message(msg)
        return to_email

    def done(res, err):
        if err:
            titulo, texto = _friendly_smtp_error(err, host)
            messagebox.showerror(titulo, texto, parent=frm.winfo_toplevel()); return
        state.cfg["smtp_teste_destino"] = res
        messagebox.showinfo("Sucesso", f"E-mail teste enviado com sucesso para {res}", parent=frm.winfo_toplevel())

    run_with_busy(frm, "Enviando e-mail de teste…", work, done)

def _valid_email(addr, frm):
    s = (addr or "").strip()
    if not s or not EMAIL_RE.match(s):
        messagebox.showwarning("E-mail", "Formato de e-mail aparentemente inválido.", parent=frm.winfo_toplevel())
        return False
    return True
