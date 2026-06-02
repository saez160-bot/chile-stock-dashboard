"""
BlueMail-style Streamlit Email Client
  • Spam filter con reglas keyword/sender/domain + heurística
  • Reglas de carpetas tipo Windows Live Mail
  • Soporte IMAP/SMTP real + modo demo con datos de muestra
"""
import streamlit as st
import json
from datetime import datetime, timedelta
import random
import re

# ── Page config (must be first) ───────────────────────────────
st.set_page_config(
    page_title="BlueMail",
    page_icon="✉️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Module imports ────────────────────────────────────────────
from modules.email_db import (
    init_db, get_accounts, add_account, delete_account,
    get_emails, get_email_by_id, upsert_email,
    mark_read, toggle_star, move_to_folder, delete_email,
    get_folder_stats, get_custom_folders, add_custom_folder,
    delete_custom_folder,
    get_spam_rules, add_spam_rule, toggle_spam_rule, delete_spam_rule,
    get_folder_rules, add_folder_rule, update_folder_rule, delete_folder_rule,
)
from modules.spam_filter import check_email, seed_default_rules
from modules.folder_rules import (
    evaluate_rules, apply_actions,
    CONDITION_FIELDS, CONDITION_OPERATORS, ACTION_TYPES,
)

# ── Initialise DB ─────────────────────────────────────────────
init_db()

# ── Custom CSS (BlueMail dark theme) ──────────────────────────
st.markdown("""
<style>
/* ── Global ── */
html, body, [data-testid="stAppViewContainer"] {
    background-color: #0d1117 !important;
    color: #e6edf3 !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
[data-testid="stSidebar"] {
    background-color: #161b22 !important;
    border-right: 1px solid #30363d;
}
[data-testid="stSidebar"] * { color: #c9d1d9 !important; }
/* ── Buttons ── */
.stButton > button {
    background: #21262d;
    color: #e6edf3;
    border: 1px solid #30363d;
    border-radius: 6px;
    transition: all .15s;
}
.stButton > button:hover {
    background: #30363d;
    border-color: #8b949e;
}
.compose-btn > button {
    background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
    color: #fff !important;
    border: none !important;
    font-weight: 600;
    border-radius: 20px !important;
    padding: 0.4rem 1.2rem !important;
}
/* ── Inputs ── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div > div {
    background: #21262d !important;
    color: #e6edf3 !important;
    border-color: #30363d !important;
}
/* ── Metrics ── */
[data-testid="stMetricValue"] { color: #388bfd !important; }
/* ── Email list row ── */
.email-row {
    padding: 10px 14px;
    border-bottom: 1px solid #21262d;
    cursor: pointer;
    border-radius: 6px;
    margin-bottom: 2px;
    transition: background .1s;
}
.email-row:hover { background: #21262d; }
.email-row.unread { border-left: 3px solid #388bfd; }
.email-row.selected { background: #1f3a5f !important; }
.email-sender { font-weight: 600; font-size: .92rem; color: #c9d1d9; }
.email-subject { font-size: .88rem; color: #8b949e; margin-top: 2px; }
.email-preview { font-size: .82rem; color: #6e7681; }
.email-meta { font-size: .78rem; color: #6e7681; float: right; }
/* ── Email reader ── */
.email-reader-header {
    padding: 16px;
    border-bottom: 1px solid #21262d;
    background: #161b22;
    border-radius: 8px;
    margin-bottom: 12px;
}
.email-reader-subject {
    font-size: 1.3rem;
    font-weight: 600;
    color: #e6edf3;
    margin-bottom: 8px;
}
.email-reader-meta {
    font-size: .85rem;
    color: #8b949e;
    line-height: 1.7;
}
.email-reader-body {
    padding: 16px;
    font-size: .92rem;
    line-height: 1.7;
    color: #c9d1d9;
    white-space: pre-wrap;
    background: #0d1117;
    border-radius: 6px;
    min-height: 200px;
}
/* ── Tag chips ── */
.tag-spam  { background:#da3633; color:#fff; padding:2px 8px; border-radius:10px; font-size:.75rem; }
.tag-star  { background:#e3b341; color:#000; padding:2px 8px; border-radius:10px; font-size:.75rem; }
.tag-read  { background:#388bfd; color:#fff; padding:2px 8px; border-radius:10px; font-size:.75rem; }
/* ── Folder badge ── */
.folder-badge {
    display:inline-block;
    background:#1f6feb;
    color:#fff;
    font-size:.7rem;
    border-radius:10px;
    padding:1px 7px;
    margin-left:4px;
}
/* ── Section headers ── */
.section-header {
    font-size:.7rem;
    font-weight:700;
    letter-spacing:.1em;
    text-transform:uppercase;
    color:#6e7681;
    padding: 12px 0 4px;
}
/* ── Dividers ── */
hr { border-color:#21262d !important; }
/* ── Rule builder ── */
.rule-card {
    background:#161b22;
    border:1px solid #30363d;
    border-radius:8px;
    padding:12px;
    margin-bottom:8px;
}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# DEMO DATA
# ═══════════════════════════════════════════════════════════════

DEMO_EMAILS = [
    {
        "uid": "demo_001", "folder": "INBOX",
        "from_addr": "pedro.gomez@empresa.cl", "from_name": "Pedro Gómez",
        "to_addr": "yo@ejemplo.com", "cc_addr": "",
        "subject": "Reunión de equipo — jueves 10:00",
        "preview": "Hola, te recuerdo que tenemos reunión de equipo el jueves a las 10:00 en la sala B.",
        "body_text": "Hola,\n\nTe recuerdo que tenemos reunión de equipo el jueves a las 10:00 en la sala B.\n\nFavor confirmar asistencia.\n\nSaludos,\nPedro",
        "body_html": "", "date": (datetime.now() - timedelta(minutes=30)).isoformat(),
        "is_read": 0, "is_starred": 0, "has_attachment": 0, "size_kb": 4,
    },
    {
        "uid": "demo_002", "folder": "INBOX",
        "from_addr": "newsletter@ofertas-online.com", "from_name": "Ofertas Online",
        "to_addr": "yo@ejemplo.com", "cc_addr": "",
        "subject": "🔥 ¡GANA DINERO YA! ¡OFERTA LIMITADA — ACTÚA AHORA!",
        "preview": "¡Haga clic aquí para ganar $10,000 gratis! Usted ha ganado nuestro sorteo especial.",
        "body_text": "¡FELICIDADES!\n\nUsted ha sido seleccionado para ganar $10,000.\nHaga clic aquí para reclamar su premio GRATIS ahora.\n¡Oferta limitada — actúe YA!",
        "body_html": "", "date": (datetime.now() - timedelta(hours=1)).isoformat(),
        "is_read": 0, "is_starred": 0, "has_attachment": 0, "size_kb": 3,
    },
    {
        "uid": "demo_003", "folder": "INBOX",
        "from_addr": "ana.silva@contabilidad.cl", "from_name": "Ana Silva",
        "to_addr": "yo@ejemplo.com", "cc_addr": "jefe@empresa.cl",
        "subject": "Informe financiero Q2 — adjunto",
        "preview": "Buenos días, adjunto encontrará el informe financiero del segundo trimestre para su revisión.",
        "body_text": "Buenos días,\n\nAdjunto encontrará el informe financiero del segundo trimestre para su revisión y aprobación.\n\nQuedo a disposición para cualquier consulta.\n\nAna Silva\nContabilidad",
        "body_html": "", "date": (datetime.now() - timedelta(hours=3)).isoformat(),
        "is_read": 1, "is_starred": 1, "has_attachment": 1, "size_kb": 245,
    },
    {
        "uid": "demo_004", "folder": "INBOX",
        "from_addr": "soporte@banco-seguro.com", "from_name": "Banco Seguro",
        "to_addr": "yo@ejemplo.com", "cc_addr": "",
        "subject": "Verificación urgente de su cuenta bancaria",
        "preview": "Su contraseña ha expirado. Verifique su cuenta inmediatamente para evitar la suspensión.",
        "body_text": "Estimado cliente,\n\nSu contraseña ha expirado. Haga clic aquí para verificar su cuenta y evitar la suspensión.\n\nEste mensaje no es spam.",
        "body_html": "", "date": (datetime.now() - timedelta(hours=5)).isoformat(),
        "is_read": 0, "is_starred": 0, "has_attachment": 0, "size_kb": 5,
    },
    {
        "uid": "demo_005", "folder": "INBOX",
        "from_addr": "github@notifications.github.com", "from_name": "GitHub",
        "to_addr": "yo@ejemplo.com", "cc_addr": "",
        "subject": "[chile-stock-dashboard] Pull request merged #42",
        "preview": "PR #42 'Feature: email app' was merged into main by saez160.",
        "body_text": "PR #42 'Feature: email app' was merged into main by saez160.\n\nView it at https://github.com/",
        "body_html": "", "date": (datetime.now() - timedelta(hours=6)).isoformat(),
        "is_read": 1, "is_starred": 0, "has_attachment": 0, "size_kb": 6,
    },
    {
        "uid": "demo_006", "folder": "INBOX",
        "from_addr": "carlos.mendez@cliente.cl", "from_name": "Carlos Méndez",
        "to_addr": "yo@ejemplo.com", "cc_addr": "",
        "subject": "Consulta sobre cotización proyecto web",
        "preview": "Buen día, me gustaría solicitar una cotización para el desarrollo de un sitio web corporativo.",
        "body_text": "Buen día,\n\nMe gustaría solicitar una cotización para el desarrollo de un sitio web corporativo con las siguientes características:\n- Diseño responsive\n- Gestión de contenidos\n- Integración con redes sociales\n\nQuedo atento a su respuesta.\n\nCarlos Méndez",
        "body_html": "", "date": (datetime.now() - timedelta(days=1)).isoformat(),
        "is_read": 0, "is_starred": 0, "has_attachment": 0, "size_kb": 3,
    },
    {
        "uid": "demo_007", "folder": "Sent",
        "from_addr": "yo@ejemplo.com", "from_name": "Yo",
        "to_addr": "pedro.gomez@empresa.cl", "cc_addr": "",
        "subject": "Re: Reunión de equipo — jueves 10:00",
        "preview": "Confirmado. Estaré presente el jueves. Saludos",
        "body_text": "Hola Pedro,\n\nConfirmado. Estaré presente el jueves.\n\nSaludos",
        "body_html": "", "date": (datetime.now() - timedelta(minutes=15)).isoformat(),
        "is_read": 1, "is_starred": 0, "has_attachment": 0, "size_kb": 2,
    },
    {
        "uid": "demo_008", "folder": "Spam",
        "from_addr": "winner@mailinator.com", "from_name": "Prize Center",
        "to_addr": "yo@ejemplo.com", "cc_addr": "",
        "subject": "You have been selected! Claim your FREE casino bonus",
        "preview": "Congratulations! Click here to claim your free casino bonus of $500.",
        "body_text": "Congratulations!\nYou have been selected to claim your FREE casino bonus of $500.\nClick here now — limited time offer!",
        "body_html": "", "date": (datetime.now() - timedelta(hours=2)).isoformat(),
        "is_read": 0, "is_starred": 0, "has_attachment": 0, "size_kb": 2,
    },
    {
        "uid": "demo_009", "folder": "Trash",
        "from_addr": "promo@tienda.cl", "from_name": "Tienda Online",
        "to_addr": "yo@ejemplo.com", "cc_addr": "",
        "subject": "Newsletter mensual — junio 2026",
        "preview": "Descubre nuestras ofertas del mes. Ropa, electrónica y más.",
        "body_text": "Descubre nuestras ofertas del mes.\nRopa, electrónica y más.\nUnsubscribe aquí.",
        "body_html": "", "date": (datetime.now() - timedelta(days=2)).isoformat(),
        "is_read": 1, "is_starred": 0, "has_attachment": 0, "size_kb": 8,
    },
]

DEMO_ACCOUNT = {
    "id": 0,
    "name": "Demo Usuario",
    "email": "yo@ejemplo.com",
    "imap_host": "", "smtp_host": "",
    "username": "", "password": "",
    "use_ssl": True,
}


def load_demo_data():
    """Insert demo emails into DB once per session."""
    for em in DEMO_EMAILS:
        upsert_email(
            account_id=0,
            uid=em["uid"],
            folder=em["folder"],
            from_addr=em["from_addr"],
            from_name=em["from_name"],
            to_addr=em["to_addr"],
            cc_addr=em.get("cc_addr", ""),
            subject=em["subject"],
            preview=em["preview"],
            body_text=em["body_text"],
            body_html=em.get("body_html", ""),
            date=em["date"],
            has_attachment=bool(em.get("has_attachment")),
            size_kb=em.get("size_kb", 0),
        )
    seed_default_rules()


# ═══════════════════════════════════════════════════════════════
# SESSION STATE
# ═══════════════════════════════════════════════════════════════

def _init_state():
    defaults = {
        "demo_loaded":       False,
        "active_account_id": 0,
        "active_folder":     "INBOX",
        "selected_email_id": None,
        "compose_open":      False,
        "compose_reply_to":  None,
        "page":              "inbox",   # inbox | spam_settings | rule_settings | accounts
        "search_query":      "",
        "syncing":           False,
        "sync_message":      "",
        "rule_edit_id":      None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

if not st.session_state.demo_loaded:
    load_demo_data()
    st.session_state.demo_loaded = True


# ═══════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════

SYSTEM_FOLDERS = [
    ("📥", "INBOX",  "Bandeja de entrada"),
    ("⭐", "Starred", "Destacados"),
    ("📤", "Sent",   "Enviados"),
    ("📝", "Drafts", "Borradores"),
    ("🗑️", "Trash",  "Papelera"),
    ("🚫", "Spam",   "Spam"),
]


def _fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        now = datetime.now()
        if dt.date() == now.date():
            return dt.strftime("%H:%M")
        if (now - dt).days < 7:
            return dt.strftime("%a")
        return dt.strftime("%d/%m")
    except Exception:
        return iso[:10] if iso else ""


def _sender_display(em: dict) -> str:
    return em.get("from_name") or em.get("from_addr", "Desconocido")


def _get_emails_for_folder(account_id, folder, search="") -> list[dict]:
    if folder == "Starred":
        emails = get_emails(account_id, "INBOX", search=search)
        emails += get_emails(account_id, "Sent", search=search)
        return [e for e in emails if e.get("is_starred")]
    return get_emails(account_id, folder, search=search)


def _apply_spam_filter_to_email(email: dict) -> bool:
    """Check spam, move if needed. Returns True if marked as spam."""
    result = check_email(
        email.get("from_addr", ""),
        email.get("subject", ""),
        email.get("body_text", ""),
    )
    if result["is_spam"] and email.get("folder") == "INBOX":
        move_to_folder(email["id"], "Spam")
        return True
    return False


def _apply_folder_rules_to_email(email: dict):
    """Evaluate and apply folder rules."""
    actions = evaluate_rules(email)
    if actions:
        apply_actions(email["id"], actions)


# ═══════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════

def render_sidebar():
    with st.sidebar:
        # Header
        st.markdown("""
        <div style='text-align:center;padding:12px 0 8px'>
          <span style='font-size:1.8rem;font-weight:700;color:#388bfd;
                       letter-spacing:-1px'>✉ BlueMail</span>
        </div>
        """, unsafe_allow_html=True)

        # Compose button
        st.markdown('<div class="compose-btn">', unsafe_allow_html=True)
        if st.button("✏️  Nuevo correo", use_container_width=True, key="compose_btn"):
            st.session_state.compose_open = True
            st.session_state.compose_reply_to = None
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("---")

        # Account picker
        accounts = get_accounts()
        all_accounts = [DEMO_ACCOUNT] + accounts
        account_names = [f"{'📧'} {a['email']}" for a in all_accounts]
        acct_idx = next(
            (i for i, a in enumerate(all_accounts)
             if a["id"] == st.session_state.active_account_id), 0
        )
        chosen = st.selectbox("Cuenta", account_names, index=acct_idx,
                              label_visibility="collapsed")
        st.session_state.active_account_id = all_accounts[account_names.index(chosen)]["id"]
        acct_id = st.session_state.active_account_id

        # Stats
        stats = get_folder_stats(acct_id)

        # System folders
        st.markdown('<p class="section-header">CARPETAS</p>', unsafe_allow_html=True)
        for icon, fkey, flabel in SYSTEM_FOLDERS:
            fstats    = stats.get(fkey, {"total": 0, "unread": 0})
            unread    = fstats.get("unread", 0)
            is_active = st.session_state.active_folder == fkey
            badge     = f'<span class="folder-badge">{unread}</span>' if unread else ""
            label_html = f"{icon} {flabel}{badge}"

            if st.button(
                f"{icon} {flabel}" + (f"  ({unread})" if unread else ""),
                key=f"folder_{fkey}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state.active_folder = fkey
                st.session_state.selected_email_id = None
                st.session_state.page = "inbox"

        # Custom folders
        custom = get_custom_folders(acct_id)
        if custom:
            st.markdown('<p class="section-header" style="margin-top:8px">MIS CARPETAS</p>',
                        unsafe_allow_html=True)
            for cf in custom:
                is_active = st.session_state.active_folder == cf["name"]
                if st.button(
                    f"{cf['icon']} {cf['name']}",
                    key=f"cfolder_{cf['id']}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    st.session_state.active_folder = cf["name"]
                    st.session_state.selected_email_id = None
                    st.session_state.page = "inbox"

        st.markdown("---")

        # Settings shortcuts
        st.markdown('<p class="section-header">AJUSTES</p>', unsafe_allow_html=True)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚫 Spam", use_container_width=True):
                st.session_state.page = "spam_settings"
        with col2:
            if st.button("📋 Reglas", use_container_width=True):
                st.session_state.page = "rule_settings"

        if st.button("➕ Cuenta / Carpeta", use_container_width=True):
            st.session_state.page = "accounts"

        # Sync button (for real accounts)
        if acct_id != 0:
            st.markdown("---")
            if st.button("🔄 Sincronizar", use_container_width=True):
                _sync_account(acct_id)


def _sync_account(account_id: int):
    """Fetch emails from IMAP and apply spam + folder rules."""
    from modules.email_client import fetch_emails as imap_fetch
    accounts = get_accounts()
    acct = next((a for a in accounts if a["id"] == account_id), None)
    if not acct:
        return
    with st.spinner("Sincronizando…"):
        for folder_imap in ("INBOX", "Sent", "Drafts"):
            emails, err = imap_fetch(acct, folder_imap, limit=50)
            if err:
                st.warning(f"Error en {folder_imap}: {err}")
                continue
            for em in emails:
                upsert_email(
                    account_id, em["uid"], folder_imap,
                    em["from_addr"], em["from_name"], em["to_addr"],
                    em["cc_addr"], em["subject"], em["preview"],
                    em["body_text"], em["body_html"], em["date"],
                    em["has_attachment"], em["size_kb"],
                )
            # Apply spam + rules to INBOX emails
            if folder_imap == "INBOX":
                cached = get_emails(account_id, "INBOX")
                for em in cached:
                    if not _apply_spam_filter_to_email(em):
                        _apply_folder_rules_to_email(em)
    st.success("Sincronización completa")


# ═══════════════════════════════════════════════════════════════
# COMPOSE MODAL
# ═══════════════════════════════════════════════════════════════

def render_compose():
    if not st.session_state.get("compose_open"):
        return

    st.markdown("---")
    st.markdown("### ✏️ Nuevo mensaje")

    reply = st.session_state.get("compose_reply_to")
    default_to      = reply.get("from_addr", "") if reply else ""
    default_subject = ("Re: " + reply.get("subject", "")) if reply else ""
    default_body    = (
        f"\n\n---\nDe: {reply.get('from_addr','')}\n"
        f"Fecha: {reply.get('date','')}\n\n{reply.get('body_text','')}"
        if reply else ""
    )

    with st.form("compose_form", clear_on_submit=True):
        c1, c2 = st.columns([3, 1])
        to_addr  = c1.text_input("Para", value=default_to)
        cc_addr  = c1.text_input("CC", value="")
        subject  = c1.text_input("Asunto", value=default_subject)
        body     = st.text_area("Mensaje", value=default_body, height=200)

        col_send, col_cancel = st.columns([1, 1])
        send   = col_send.form_submit_button("📤 Enviar", type="primary")
        cancel = col_cancel.form_submit_button("✖ Cancelar")

    if send:
        if not to_addr.strip():
            st.error("Ingresa un destinatario")
        else:
            acct_id = st.session_state.active_account_id
            if acct_id == 0:
                # Demo mode — just save to Sent
                upsert_email(
                    0, f"sent_{datetime.now().timestamp()}", "Sent",
                    DEMO_ACCOUNT["email"], DEMO_ACCOUNT["name"],
                    to_addr, cc_addr, subject,
                    body[:200], body, "", datetime.now().isoformat(),
                )
                st.success("✅ Mensaje guardado (modo demo)")
            else:
                accounts = get_accounts()
                acct = next((a for a in accounts if a["id"] == acct_id), None)
                if acct:
                    from modules.email_client import send_email
                    ok, msg = send_email(acct, to_addr, subject, body, cc_addr)
                    if ok:
                        st.success("✅ Enviado")
                    else:
                        st.error(f"Error: {msg}")
            st.session_state.compose_open = False
            st.rerun()

    if cancel:
        st.session_state.compose_open = False
        st.rerun()


# ═══════════════════════════════════════════════════════════════
# EMAIL LIST PANEL
# ═══════════════════════════════════════════════════════════════

def render_email_list(acct_id: int, folder: str, search: str):
    emails = _get_emails_for_folder(acct_id, folder, search)

    st.markdown(
        f"<div style='font-size:.75rem;color:#6e7681;margin-bottom:6px'>"
        f"{len(emails)} mensaje{'s' if len(emails)!=1 else ''}</div>",
        unsafe_allow_html=True
    )

    if not emails:
        st.markdown(
            "<div style='text-align:center;color:#6e7681;padding:40px 0;'>"
            "📭 Sin mensajes</div>",
            unsafe_allow_html=True
        )
        return

    for em in emails:
        is_unread   = not em.get("is_read")
        is_selected = em["id"] == st.session_state.selected_email_id
        is_starred  = em.get("is_starred")
        is_spam     = em.get("is_spam")

        sender  = _sender_display(em)
        subj    = em.get("subject", "(sin asunto)")
        preview = em.get("preview", "")[:80]
        date_s  = _fmt_date(em.get("date", ""))

        # Build row with a button
        star_icon = "⭐" if is_starred else "·"
        unread_dot = "🔵 " if is_unread else "   "
        btn_label = f"{unread_dot}{star_icon}  **{sender[:28]}**   {date_s}\n{subj[:50]}"

        if st.button(btn_label, key=f"em_{em['id']}", use_container_width=True):
            st.session_state.selected_email_id = em["id"]
            if is_unread:
                mark_read(em["id"], True)
            st.rerun()


# ═══════════════════════════════════════════════════════════════
# EMAIL READER
# ═══════════════════════════════════════════════════════════════

def render_email_reader():
    eid = st.session_state.selected_email_id
    if not eid:
        st.markdown(
            "<div style='text-align:center;color:#6e7681;padding:60px 20px;'>"
            "<div style='font-size:3rem'>📬</div>"
            "<div style='margin-top:8px'>Selecciona un mensaje para leerlo</div>"
            "</div>",
            unsafe_allow_html=True
        )
        return

    em = get_email_by_id(eid)
    if not em:
        st.warning("Mensaje no encontrado")
        return

    # ── Action bar ───────────────────────────────────────────
    col_r, col_fw, col_star, col_spam, col_del, col_move = st.columns([1,1,1,1,1,2])

    with col_r:
        if st.button("↩ Responder", key="btn_reply"):
            st.session_state.compose_open = True
            st.session_state.compose_reply_to = em
            st.rerun()

    with col_fw:
        if st.button("→ Reenviar", key="btn_fwd"):
            st.session_state.compose_open = True
            st.session_state.compose_reply_to = {
                **em,
                "from_addr": "",
                "subject": "Fwd: " + em.get("subject", ""),
            }
            st.rerun()

    with col_star:
        star_lbl = "⭐ Quitar" if em.get("is_starred") else "☆ Destacar"
        if st.button(star_lbl, key="btn_star"):
            toggle_star(eid)
            st.rerun()

    with col_spam:
        spam_lbl = "✅ No spam" if em.get("folder") == "Spam" else "🚫 Spam"
        if st.button(spam_lbl, key="btn_spam"):
            if em.get("folder") == "Spam":
                move_to_folder(eid, "INBOX")
            else:
                move_to_folder(eid, "Spam")
            st.session_state.selected_email_id = None
            st.rerun()

    with col_del:
        if st.button("🗑 Eliminar", key="btn_del"):
            delete_email(eid)
            st.session_state.selected_email_id = None
            st.rerun()

    with col_move:
        acct_id = st.session_state.active_account_id
        custom  = get_custom_folders(acct_id)
        folder_opts = [f[2] for f in SYSTEM_FOLDERS if f[1] not in ("Starred",)] + \
                      [cf["name"] for cf in custom]
        move_to = st.selectbox("📁 Mover a…", ["—"] + folder_opts,
                               key="move_sel", label_visibility="collapsed")
        if move_to != "—":
            # Map label→key
            sys_map = {f[2]: f[1] for f in SYSTEM_FOLDERS}
            target = sys_map.get(move_to, move_to)
            move_to_folder(eid, target)
            st.session_state.selected_email_id = None
            st.rerun()

    st.markdown("---")

    # ── Header ───────────────────────────────────────────────
    subj     = em.get("subject", "(sin asunto)")
    from_n   = em.get("from_name", "")
    from_a   = em.get("from_addr", "")
    to_a     = em.get("to_addr", "")
    cc_a     = em.get("cc_addr", "")
    date_s   = _fmt_date(em.get("date", ""))
    has_att  = em.get("has_attachment")

    tags_html = ""
    if em.get("is_starred"):
        tags_html += '<span class="tag-star">⭐ Destacado</span> '
    if em.get("folder") == "Spam":
        tags_html += '<span class="tag-spam">🚫 Spam</span> '
    if has_att:
        tags_html += '<span class="tag-read">📎 Adjunto</span> '

    st.markdown(f"""
    <div class="email-reader-header">
      <div class="email-reader-subject">{subj}</div>
      {tags_html}
      <div class="email-reader-meta">
        <b>De:</b> {from_n} &lt;{from_a}&gt;<br>
        <b>Para:</b> {to_a}{f'<br><b>CC:</b> {cc_a}' if cc_a else ''}<br>
        <b>Fecha:</b> {em.get('date','')[:19].replace('T',' ')}
      </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Body ─────────────────────────────────────────────────
    body_html = em.get("body_html", "")
    body_text = em.get("body_text", "")

    if body_html:
        # Render HTML in an iframe-style container
        st.components.v1.html(
            f"""<div style="background:#0d1117;color:#c9d1d9;
                            font-family:sans-serif;font-size:14px;
                            padding:16px;border-radius:6px;">
                {body_html}
                </div>""",
            height=400, scrolling=True
        )
    else:
        st.markdown(
            f'<div class="email-reader-body">{body_text or "(sin contenido)"}</div>',
            unsafe_allow_html=True
        )


# ═══════════════════════════════════════════════════════════════
# SPAM SETTINGS PAGE
# ═══════════════════════════════════════════════════════════════

def render_spam_settings():
    st.markdown("## 🚫 Filtro de spam")
    st.caption("Reglas que determinan qué mensajes se mueven a la carpeta Spam.")

    # ── Add rule ─────────────────────────────────────────────
    with st.expander("➕ Agregar nueva regla", expanded=False):
        with st.form("add_spam_rule"):
            c1, c2, c3 = st.columns([2, 3, 2])
            rule_type = c1.selectbox("Tipo", [
                "sender", "domain", "keyword_subject", "keyword_body", "whitelist_sender"
            ], format_func=lambda x: {
                "sender":            "Remitente (email)",
                "domain":            "Dominio",
                "keyword_subject":   "Palabra clave — Asunto",
                "keyword_body":      "Palabra clave — Cuerpo",
                "whitelist_sender":  "✅ Siempre permitir (remitente)",
            }.get(x, x))
            value  = c2.text_input("Valor", placeholder="ej. spam@ejemplo.com")
            action = c3.selectbox("Acción", ["spam", "delete"],
                                  format_func=lambda x: {"spam": "Mover a Spam",
                                                          "delete": "Eliminar"}.get(x, x))
            if st.form_submit_button("Agregar regla"):
                if value.strip():
                    add_spam_rule(rule_type, value.strip(), action)
                    st.success("Regla agregada")
                    st.rerun()
                else:
                    st.error("Ingresa un valor")

    # ── Existing rules ────────────────────────────────────────
    rules = get_spam_rules()
    type_labels = {
        "sender":           "Remitente",
        "domain":           "Dominio",
        "keyword_subject":  "Kw Asunto",
        "keyword_body":     "Kw Cuerpo",
        "whitelist_sender": "✅ Permitir",
    }
    action_labels = {"spam": "→ Spam", "delete": "Eliminar", "inbox": "→ Inbox"}

    if not rules:
        st.info("Sin reglas. Agrega una arriba o usa el botón 'Cargar defaults'.")
    else:
        st.markdown(f"**{len(rules)} regla(s) configurada(s)**")
        for r in rules:
            enabled_icon = "🟢" if r["enabled"] else "🔴"
            c1, c2, c3, c4, c5 = st.columns([1.5, 3, 1.5, 1, 1])
            c1.markdown(f"`{type_labels.get(r['rule_type'], r['rule_type'])}`")
            c2.markdown(f"**{r['value']}**")
            c3.markdown(f"{action_labels.get(r['action'], r['action'])} · {r['hits']} hits")
            if c4.button(enabled_icon, key=f"togsp_{r['id']}", help="Activar/desactivar"):
                toggle_spam_rule(r["id"])
                st.rerun()
            if c5.button("🗑", key=f"delsp_{r['id']}", help="Eliminar regla"):
                delete_spam_rule(r["id"])
                st.rerun()

    st.markdown("---")

    # ── Run filter on inbox ───────────────────────────────────
    c1, c2 = st.columns(2)
    if c1.button("🔍 Aplicar filtro a Bandeja de entrada", type="primary"):
        acct_id = st.session_state.active_account_id
        inbox   = get_emails(acct_id, "INBOX")
        moved   = 0
        for em in inbox:
            if _apply_spam_filter_to_email(em):
                moved += 1
        st.success(f"Filtro aplicado. {moved} mensaje(s) movidos a Spam.")
        st.rerun()

    if c2.button("📥 Cargar reglas por defecto"):
        seed_default_rules()
        st.success("Reglas por defecto cargadas")
        st.rerun()


# ═══════════════════════════════════════════════════════════════
# FOLDER RULES PAGE  (Windows Live Mail style)
# ═══════════════════════════════════════════════════════════════

def render_rule_settings():
    st.markdown("## 📋 Reglas de carpetas")
    st.caption("Organiza automáticamente los mensajes según condiciones — similar a Windows Live Mail.")

    tab_list, tab_new = st.tabs(["📋 Reglas activas", "➕ Nueva regla"])

    # ── Active rules tab ──────────────────────────────────────
    with tab_list:
        rules = get_folder_rules()
        if not rules:
            st.info("Sin reglas. Crea una en la pestaña 'Nueva regla'.")
        for rule in rules:
            enabled_icon = "🟢" if rule["enabled"] else "🔴"
            with st.expander(
                f"{enabled_icon} [{rule['priority']}] {rule['name']}  "
                f"· {len(rule['conditions'])} cond. · {len(rule['actions'])} acc. "
                f"· {rule['hits']} hits",
                expanded=False
            ):
                # Show conditions
                st.markdown(f"**Lógica:** `{rule['condition_logic']}`")
                st.markdown("**Condiciones:**")
                for c in rule["conditions"]:
                    field_lbl = CONDITION_FIELDS.get(c["field"], c["field"])
                    op_lbl    = CONDITION_OPERATORS.get(c["operator"], c["operator"])
                    st.markdown(f"- {field_lbl} **{op_lbl}** `{c['value']}`")
                st.markdown("**Acciones:**")
                for a in rule["actions"]:
                    st.markdown(f"- {ACTION_TYPES.get(a['type'], a['type'])}: **{a.get('value', '')}**")

                col_en, col_del = st.columns([1, 1])
                if col_en.button(
                    "✅ Activar" if not rule["enabled"] else "⛔ Desactivar",
                    key=f"en_rule_{rule['id']}"
                ):
                    update_folder_rule(
                        rule["id"], rule["name"],
                        rule["conditions"], rule["actions"],
                        rule["condition_logic"], rule["priority"],
                        not rule["enabled"], rule.get("stop_processing", False)
                    )
                    st.rerun()
                if col_del.button("🗑 Eliminar", key=f"del_rule_{rule['id']}"):
                    delete_folder_rule(rule["id"])
                    st.rerun()

        if rules:
            st.markdown("---")
            if st.button("▶ Aplicar todas las reglas a Bandeja de entrada", type="primary"):
                acct_id = st.session_state.active_account_id
                inbox   = get_emails(acct_id, "INBOX")
                applied = 0
                for em in inbox:
                    actions = evaluate_rules(em)
                    if actions:
                        apply_actions(em["id"], actions)
                        applied += 1
                st.success(f"Reglas aplicadas a {applied} mensaje(s).")
                st.rerun()

    # ── New rule tab ──────────────────────────────────────────
    with tab_new:
        st.markdown("### Crear nueva regla")

        if "new_conditions" not in st.session_state:
            st.session_state.new_conditions = [
                {"field": "from", "operator": "contains", "value": ""}
            ]
        if "new_actions" not in st.session_state:
            st.session_state.new_actions = [
                {"type": "move", "value": "INBOX"}
            ]

        name          = st.text_input("Nombre de la regla", placeholder="Ej: Mover correos del jefe")
        cond_logic    = st.radio("Lógica de condiciones", ["AND", "OR"],
                                 horizontal=True,
                                 help="AND = todas deben cumplirse; OR = al menos una")
        priority      = st.number_input("Prioridad (menor = primero)", 0, 99, 0)
        stop_proc     = st.checkbox("Detener procesamiento de reglas posteriores al cumplir esta")

        st.markdown("#### Condiciones")
        conds = st.session_state.new_conditions
        for i, cond in enumerate(conds):
            c1, c2, c3, c4 = st.columns([2, 2, 3, 0.5])
            cond["field"]    = c1.selectbox("Campo", list(CONDITION_FIELDS.keys()),
                                             index=list(CONDITION_FIELDS.keys()).index(cond.get("field", "from")),
                                             key=f"cond_field_{i}",
                                             format_func=lambda k: CONDITION_FIELDS[k])
            cond["operator"] = c2.selectbox("Operador", list(CONDITION_OPERATORS.keys()),
                                             index=list(CONDITION_OPERATORS.keys()).index(cond.get("operator", "contains")),
                                             key=f"cond_op_{i}",
                                             format_func=lambda k: CONDITION_OPERATORS[k])
            if cond["field"] in ("has_attach",):
                cond["value"] = c3.selectbox("Valor", ["true", "false"],
                                              key=f"cond_val_{i}")
            elif cond["field"] in ("size_kb",):
                cond["value"] = str(c3.number_input("KB", 0, 99999,
                                                     int(cond.get("value", 0) or 0),
                                                     key=f"cond_val_{i}"))
            else:
                cond["value"] = c3.text_input("Valor", value=cond.get("value", ""),
                                               key=f"cond_val_{i}")
            if c4.button("✖", key=f"rm_cond_{i}") and len(conds) > 1:
                conds.pop(i)
                st.rerun()

        if st.button("➕ Agregar condición"):
            conds.append({"field": "subject", "operator": "contains", "value": ""})
            st.rerun()

        st.markdown("#### Acciones")
        acts = st.session_state.new_actions
        acct_id = st.session_state.active_account_id
        custom  = get_custom_folders(acct_id)
        folder_opts = [f[1] for f in SYSTEM_FOLDERS if f[1] != "Starred"] + \
                      [cf["name"] for cf in custom]

        for j, act in enumerate(acts):
            a1, a2, a3 = st.columns([2, 3, 0.5])
            act["type"] = a1.selectbox("Acción", list(ACTION_TYPES.keys()),
                                        index=list(ACTION_TYPES.keys()).index(act.get("type", "move")),
                                        key=f"act_type_{j}",
                                        format_func=lambda k: ACTION_TYPES[k])
            if act["type"] in ("move", "copy"):
                act["value"] = a2.selectbox("Carpeta destino", folder_opts,
                                             index=folder_opts.index(act["value"])
                                             if act.get("value") in folder_opts else 0,
                                             key=f"act_val_{j}")
            elif act["type"] == "forward":
                act["value"] = a2.text_input("Dirección de reenvío",
                                              value=act.get("value", ""),
                                              key=f"act_val_{j}")
            else:
                a2.markdown(f"*{ACTION_TYPES[act['type']]}*")
                act["value"] = ""
            if a3.button("✖", key=f"rm_act_{j}") and len(acts) > 1:
                acts.pop(j)
                st.rerun()

        if st.button("➕ Agregar acción"):
            acts.append({"type": "mark_read", "value": ""})
            st.rerun()

        st.markdown("---")
        if st.button("💾 Guardar regla", type="primary"):
            if not name.strip():
                st.error("Ingresa un nombre para la regla")
            elif not any(c.get("value") for c in conds
                         if conds[0].get("field") not in ("has_attach",)):
                st.error("Completa al menos una condición")
            else:
                add_folder_rule(name.strip(), conds, acts, cond_logic, priority, stop_proc)
                st.success(f"Regla '{name}' guardada")
                del st.session_state["new_conditions"]
                del st.session_state["new_actions"]
                st.rerun()


# ═══════════════════════════════════════════════════════════════
# ACCOUNTS PAGE
# ═══════════════════════════════════════════════════════════════

def render_accounts():
    st.markdown("## ⚙️ Cuentas y carpetas")

    tab_accts, tab_folders = st.tabs(["📧 Cuentas de correo", "📁 Carpetas personalizadas"])

    with tab_accts:
        accounts = get_accounts()
        if accounts:
            st.markdown("### Cuentas configuradas")
            for a in accounts:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"**{a['name']}** — `{a['email']}` · {a['imap_host']}")
                if c2.button("🗑 Eliminar", key=f"del_acct_{a['id']}"):
                    delete_account(a["id"])
                    st.rerun()
        else:
            st.info("Sólo hay cuenta demo. Agrega tu cuenta real abajo.")

        st.markdown("### ➕ Agregar cuenta")
        presets = {
            "Gmail":           ("imap.gmail.com", "smtp.gmail.com", 993, 587),
            "Outlook / Hotmail": ("outlook.office365.com", "smtp.office365.com", 993, 587),
            "Yahoo":           ("imap.mail.yahoo.com", "smtp.mail.yahoo.com", 993, 587),
            "Personalizado":   ("", "", 993, 587),
        }
        preset_name = st.selectbox("Proveedor", list(presets.keys()))
        imap_h, smtp_h, imap_p, smtp_p = presets[preset_name]

        with st.form("add_account_form"):
            c1, c2 = st.columns(2)
            acc_name  = c1.text_input("Nombre para mostrar", placeholder="Mi cuenta Gmail")
            acc_email = c2.text_input("Dirección de correo")
            imap_host = c1.text_input("Servidor IMAP", value=imap_h)
            smtp_host = c2.text_input("Servidor SMTP", value=smtp_h)
            imap_port = c1.number_input("Puerto IMAP", value=imap_p)
            smtp_port = c2.number_input("Puerto SMTP", value=smtp_p)
            username  = c1.text_input("Usuario (normalmente tu email)")
            password  = c2.text_input("Contraseña", type="password",
                                       help="Gmail: usa una Contraseña de Aplicación")
            use_ssl   = st.checkbox("Usar SSL", value=True)

            if st.form_submit_button("Agregar cuenta", type="primary"):
                if not acc_email or not password:
                    st.error("Email y contraseña son obligatorios")
                else:
                    ok, msg = add_account(
                        acc_name or acc_email, acc_email,
                        imap_host, smtp_host,
                        username or acc_email, password,
                        int(imap_port), int(smtp_port), use_ssl
                    )
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    with tab_folders:
        acct_id = st.session_state.active_account_id
        custom  = get_custom_folders(acct_id)

        if custom:
            st.markdown("### Carpetas actuales")
            for cf in custom:
                c1, c2 = st.columns([4, 1])
                c1.markdown(f"{cf['icon']} **{cf['name']}**")
                if c2.button("🗑", key=f"del_cf_{cf['id']}"):
                    delete_custom_folder(cf["id"])
                    st.rerun()

        st.markdown("### ➕ Nueva carpeta")
        with st.form("add_folder_form"):
            icon_choices = ["📁", "📂", "🗂️", "📌", "🔖", "💼", "🏠", "❤️", "🔔"]
            c1, c2, c3 = st.columns([1, 3, 1])
            icon = c1.selectbox("Icono", icon_choices)
            name = c2.text_input("Nombre")
            if c3.form_submit_button("Crear"):
                if name.strip():
                    ok = add_custom_folder(acct_id, name.strip(), icon)
                    if ok:
                        st.success(f"Carpeta '{name}' creada")
                        st.rerun()
                    else:
                        st.error("Ya existe una carpeta con ese nombre")
                else:
                    st.error("Ingresa un nombre")


# ═══════════════════════════════════════════════════════════════
# MAIN LAYOUT
# ═══════════════════════════════════════════════════════════════

render_sidebar()

page = st.session_state.page

if page == "spam_settings":
    render_spam_settings()

elif page == "rule_settings":
    render_rule_settings()

elif page == "accounts":
    render_accounts()

else:
    # Inbox / folder view
    folder  = st.session_state.active_folder
    acct_id = st.session_state.active_account_id

    folder_labels = {f[1]: f[2] for f in SYSTEM_FOLDERS}
    folder_label  = folder_labels.get(folder, folder)

    # Top bar
    top_left, top_search, top_right = st.columns([2, 4, 1])
    with top_left:
        st.markdown(
            f"<h3 style='margin:0;color:#e6edf3'>{folder_label}</h3>",
            unsafe_allow_html=True
        )
    with top_search:
        st.session_state.search_query = st.text_input(
            "Buscar", value=st.session_state.search_query,
            placeholder="🔍 Buscar mensajes…",
            label_visibility="collapsed"
        )
    with top_right:
        if st.button("🔄", help="Actualizar"):
            st.rerun()

    # Compose if open
    if st.session_state.compose_open:
        render_compose()
        st.markdown("---")

    # Split layout: email list | email reader
    list_col, reader_col = st.columns([1, 2])

    with list_col:
        render_email_list(acct_id, folder, st.session_state.search_query)

    with reader_col:
        render_email_reader()
