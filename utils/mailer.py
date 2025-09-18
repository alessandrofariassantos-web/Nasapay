# utils/mailer.py
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import make_msgid, formataddr
from typing import Iterable, Optional, Tuple, Dict

def _coerce_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    s = (str(v or "")).strip().lower()
    return s in {"1", "true", "t", "yes", "y", "sim", "on"}

def send_email_with_attachments(
    params: Dict,
    to: str,
    subject: str,
    body: str,
    attachments: Iterable[str],
    from_name: Optional[str] = None,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Envia um e-mail (texto simples) com anexos PDF.
    Retorna (ok, message_id, error).
    """
    to = (to or "").strip()
    if not to:
        return (False, None, "Destinatário vazio.")

    # --- credenciais/servidor
    from_addr = (params.get("smtp_email") or "").strip()
    host      = (params.get("smtp_host")  or "").strip()
    porta     = int(str(params.get("smtp_porta") or "587"))
    usuario   = (params.get("smtp_usuario") or from_addr).strip()
    senha     = (params.get("smtp_senha")   or "").strip()
    modo      = (params.get("smtp_tls_ssl") or "TLS").strip().upper()  # "TLS" ou "SSL"
    requer_auth = _coerce_bool(params.get("smtp_requer_auth", True))

    if not from_addr or not host or not porta:
        return (False, None, "Configuração de e-mail incompleta (ver aba Conta E-mail).")

    # --- mensagem
    msg = EmailMessage()
    display_from = formataddr((from_name or "", from_addr)) if from_name else from_addr
    msg["From"] = display_from
    msg["To"] = to
    msg["Subject"] = subject.strip() if subject else "(sem assunto)"
    msg["Message-ID"] = make_msgid()
    msg.set_content(body or "", subtype="plain", charset="utf-8")

    # anexos
    for path in attachments or []:
        if not path:
            continue
        apath = os.path.normpath(path)
        try:
            with open(apath, "rb") as f:
                data = f.read()
            filename = os.path.basename(apath)
            msg.add_attachment(
                data,
                maintype="application",
                subtype="pdf",
                filename=filename,
            )
        except Exception as e:
            return (False, None, f"Falha ao anexar '{apath}': {e}")

    try:
        if modo == "SSL":
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(host, porta, context=context) as smtp:
                if requer_auth:
                    smtp.login(usuario, senha)
                resp = smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, porta) as smtp:
                smtp.ehlo()
                try:
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.ehlo()
                except Exception:
                    # alguns servidores já exigem TLS implícito; tenta seguir sem STARTTLS
                    pass
                if requer_auth:
                    smtp.login(usuario, senha)
                resp = smtp.send_message(msg)

        # smtplib não retorna message-id; usamos o nosso
        return (True, msg["Message-ID"], None)
    except Exception as e:
        return (False, None, f"Falha ao enviar e-mail: {e}")
