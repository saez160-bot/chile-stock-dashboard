"""
IMAP / SMTP email client.
Falls back gracefully — if IMAP fails, returns an empty list so the UI
still works with locally cached / demo emails.
"""
import imaplib
import smtplib
import email as email_lib
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import ssl
from datetime import datetime
from typing import Optional


def _decode_header_value(raw) -> str:
    if raw is None:
        return ""
    parts = decode_header(str(raw))
    decoded = []
    for part, charset in parts:
        if isinstance(part, bytes):
            try:
                decoded.append(part.decode(charset or "utf-8", errors="replace"))
            except Exception:
                decoded.append(part.decode("latin-1", errors="replace"))
        else:
            decoded.append(str(part))
    return " ".join(decoded)


def _get_body(msg) -> tuple[str, str]:
    """Return (text_plain, text_html)."""
    text_plain = ""
    text_html  = ""
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                continue
            payload = part.get_payload(decode=True)
            if payload is None:
                continue
            charset = part.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("latin-1", errors="replace")
            if ct == "text/plain" and not text_plain:
                text_plain = text
            elif ct == "text/html" and not text_html:
                text_html = text
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            try:
                text = payload.decode(charset, errors="replace")
            except Exception:
                text = payload.decode("latin-1", errors="replace")
            if msg.get_content_type() == "text/html":
                text_html = text
            else:
                text_plain = text
    return text_plain, text_html


def _has_attachment(msg) -> bool:
    if msg.is_multipart():
        for part in msg.walk():
            if "attachment" in str(part.get("Content-Disposition", "")):
                return True
    return False


def connect_imap(account: dict):
    """Return (imap, None) or (None, error_str)."""
    try:
        host = account["imap_host"]
        port = int(account.get("imap_port", 993))
        use_ssl = bool(account.get("use_ssl", True))
        if use_ssl:
            ctx = ssl.create_default_context()
            imap = imaplib.IMAP4_SSL(host, port, ssl_context=ctx)
        else:
            imap = imaplib.IMAP4(host, port)
        imap.login(account["username"], account["password"])
        return imap, None
    except Exception as e:
        return None, str(e)


def fetch_folder_list(account: dict) -> list[str]:
    imap, err = connect_imap(account)
    if err:
        return []
    try:
        _, folders_raw = imap.list()
        names = []
        for f in folders_raw:
            if f:
                parts = f.decode().split('"/"')
                if parts:
                    names.append(parts[-1].strip().strip('"'))
        return names
    except Exception:
        return []
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def fetch_emails(account: dict, folder: str = "INBOX",
                 limit: int = 50) -> tuple[list[dict], Optional[str]]:
    """
    Returns (list_of_email_dicts, error_or_None).
    Each dict: uid, from_addr, from_name, to_addr, cc_addr, subject,
               preview, body_text, body_html, date, has_attachment, size_kb
    """
    imap, err = connect_imap(account)
    if err:
        return [], err

    emails = []
    try:
        typ, _ = imap.select(folder, readonly=True)
        if typ != "OK":
            return [], f"Cannot select {folder}"

        _, data = imap.search(None, "ALL")
        all_uids = data[0].split()
        # Most recent first, limited
        uids = all_uids[-limit:][::-1]

        for uid in uids:
            try:
                _, msg_data = imap.fetch(uid, "(RFC822 RFC822.SIZE)")
                raw_email = msg_data[0][1]
                size_bytes = 0
                if len(msg_data) > 1:
                    try:
                        size_bytes = int(msg_data[1])
                    except Exception:
                        pass

                msg = email_lib.message_from_bytes(raw_email)
                from_raw   = msg.get("From", "")
                to_raw     = msg.get("To", "")
                cc_raw     = msg.get("Cc", "")
                subject    = _decode_header_value(msg.get("Subject", "(sin asunto)"))
                date_str   = msg.get("Date", "")
                body_text, body_html = _get_body(msg)
                has_attach = _has_attachment(msg)

                # Parse from
                from_name  = ""
                from_addr  = ""
                addr_parts = from_raw.split("<")
                if len(addr_parts) == 2:
                    from_name = _decode_header_value(addr_parts[0].strip().strip('"'))
                    from_addr = addr_parts[1].rstrip(">").strip()
                else:
                    from_addr = _decode_header_value(from_raw).strip()

                preview = (body_text or "").replace("\n", " ").strip()[:200]

                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(date_str)
                    date_iso = dt.isoformat()
                except Exception:
                    date_iso = date_str

                emails.append({
                    "uid":            uid.decode(),
                    "from_addr":      from_addr,
                    "from_name":      from_name,
                    "to_addr":        _decode_header_value(to_raw),
                    "cc_addr":        _decode_header_value(cc_raw),
                    "subject":        subject,
                    "preview":        preview,
                    "body_text":      body_text,
                    "body_html":      body_html,
                    "date":           date_iso,
                    "has_attachment": has_attach,
                    "size_kb":        round(size_bytes / 1024, 1),
                })
            except Exception:
                continue
    except Exception as e:
        return emails, str(e)
    finally:
        try:
            imap.logout()
        except Exception:
            pass

    return emails, None


def send_email(account: dict, to: str, subject: str, body: str,
               cc: str = "", reply_to: str = "") -> tuple[bool, str]:
    try:
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"{account['name']} <{account['email']}>"
        msg["To"]      = to
        msg["Subject"] = subject
        if cc:
            msg["Cc"] = cc
        if reply_to:
            msg["Reply-To"] = reply_to
        msg.attach(MIMEText(body, "plain", "utf-8"))

        host = account["smtp_host"]
        port = int(account.get("smtp_port", 587))

        with smtplib.SMTP(host, port, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.login(account["username"], account["password"])
            recipients = [to] + ([cc] if cc else [])
            s.sendmail(account["email"], recipients, msg.as_string())
        return True, "Enviado"
    except Exception as e:
        return False, str(e)
