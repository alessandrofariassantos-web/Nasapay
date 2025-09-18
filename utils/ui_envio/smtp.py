# utils/ui_envio/smtp.py
import os, ssl, smtplib, mimetypes, email.utils, uuid
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email import encoders

def _from_header(cfg: dict) -> str:
    nome = (cfg.get("smtp_nome_remetente") or cfg.get("razao_social") or "").strip()
    mail = (cfg.get("smtp_email") or cfg.get("smtp_usuario") or "").strip()
    if not mail:
        raise RuntimeError("Remetente não configurado (smtp_email/usuario).")
    return email.utils.formataddr((nome, mail)) if nome else mail

def img_to_cid(path: str):
    """Retorna (cid, mimetype, bytes) para imagem inline."""
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    with open(path, "rb") as f:
        data = f.read()
    ctype, _ = mimetypes.guess_type(path)
    if not ctype: ctype = "application/octet-stream"
    cid = f"{uuid.uuid4().hex}@nasapay"
    return cid, ctype, data

def _attach_inline(root: MIMEMultipart, inline):
    if not inline: return
    for item in inline:
        # aceita tanto tupla quanto dict
        if isinstance(item, (list, tuple)) and len(item) >= 4:
            _kind, cid, ctype, data = item[0], item[1], item[2], item[3]
        elif isinstance(item, dict):
            cid   = item.get("cid") or item.get("id")
            ctype = item.get("ctype") or "application/octet-stream"
            data  = item.get("data") or b""
        else:
            continue
        maintype, subtype = (ctype.split("/", 1) if "/" in (ctype or "") else ("application", "octet-stream"))
        if maintype == "image":
            part = MIMEImage(data, _subtype=subtype)
        else:
            part = MIMEBase(maintype, subtype)
            part.set_payload(data); encoders.encode_base64(part)
        part.add_header("Content-ID", f"<{cid}>")
        part.add_header("Content-Disposition", "inline", filename=cid)
        root.attach(part)

def _attach_files(root: MIMEMultipart, files):
    if not files: return
    for path in files:
        try:
            with open(path, "rb") as f:
                data = f.read()
        except Exception:
            # ignora anexo inválido e continua
            continue
        ctype, _ = mimetypes.guess_type(path)
        maintype, subtype = (ctype.split("/",1) if ctype and "/" in ctype else ("application","octet-stream"))
        if maintype == "image":
            part = MIMEImage(data, _subtype=subtype)
        else:
            part = MIMEBase(maintype, subtype)
            part.set_payload(data); encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=os.path.basename(path))
        root.attach(part)

def _smtp_connect(cfg: dict):
    host = (cfg.get("smtp_host") or "").strip()
    porta = int(str(cfg.get("smtp_porta") or "0") or "0")
    modo = (cfg.get("smtp_tls_ssl") or "TLS").upper().strip()  # TLS | SSL | NENHUM
    user = (cfg.get("smtp_usuario") or cfg.get("smtp_email") or "").strip()
    pwd  = (cfg.get("smtp_senha") or "").strip()
    auth = bool(cfg.get("smtp_requer_auth", True))

    if not host or not porta:
        raise RuntimeError("Servidor/porta SMTP não configurados.")

    if modo == "SSL":
        ctx = ssl.create_default_context()
        server = smtplib.SMTP_SSL(host, porta, context=ctx, timeout=30)
    else:
        server = smtplib.SMTP(host, porta, timeout=30)
        server.ehlo()
        if modo == "TLS":
            ctx = ssl.create_default_context()
            server.starttls(context=ctx)
    if auth:
        server.login(user, pwd)
    return server

def send_html(cfg: dict, to_addr: str, subject: str, html: str, inline=None, files=None):
    inline = inline or []
    files  = files or []

    msg_root = MIMEMultipart("related")
    msg_root["From"]    = _from_header(cfg)
    msg_root["To"]      = to_addr
    msg_root["Subject"] = subject

    alt = MIMEMultipart("alternative")
    msg_root.attach(alt)
    alt.attach(MIMEText("Este e-mail possui conteúdo HTML.", "plain", "utf-8"))
    alt.attach(MIMEText(html or "", "html", "utf-8"))

    _attach_inline(msg_root, inline)
    _attach_files(msg_root, files)

    server = _smtp_connect(cfg)
    try:
        server.sendmail(msg_root["From"], [to_addr], msg_root.as_string())
    finally:
        try: server.quit()
        except Exception: pass
