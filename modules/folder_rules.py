"""
Folder rules engine — similar to Windows Live Mail message rules.

Each rule has:
  name           : str
  condition_logic: 'AND' | 'OR'
  conditions     : list of {field, operator, value}
  actions        : list of {type, value}
  priority       : int  (lower = applied first)
  enabled        : bool
  stop_processing: bool  (stop after this rule fires)
"""
import re
from .email_db import get_folder_rules, increment_rule_hits

# ── Condition fields ──────────────────────────────────────────
CONDITION_FIELDS = {
    "from":       "Remitente (De:)",
    "to":         "Destinatario (Para:)",
    "subject":    "Asunto",
    "body":       "Cuerpo del mensaje",
    "has_attach": "Tiene adjunto",
    "size_kb":    "Tamaño (KB)",
}

CONDITION_OPERATORS = {
    "contains":     "contiene",
    "not_contains": "no contiene",
    "is":           "es exactamente",
    "starts_with":  "empieza con",
    "ends_with":    "termina con",
    "regex":        "coincide con regex",
    "gt":           ">  (mayor que)",
    "lt":           "<  (menor que)",
}

# ── Action types ──────────────────────────────────────────────
ACTION_TYPES = {
    "move":      "Mover a carpeta",
    "copy":      "Copiar a carpeta",
    "mark_read": "Marcar como leído",
    "mark_star": "Marcar con estrella",
    "mark_spam": "Marcar como spam",
    "delete":    "Eliminar",
    "forward":   "Reenviar a",
}


def _eval_condition(cond: dict, email: dict) -> bool:
    field    = cond.get("field", "")
    operator = cond.get("operator", "contains")
    value    = str(cond.get("value", "")).lower().strip()

    if field == "has_attach":
        email_val = bool(email.get("has_attachment"))
        return email_val == (value in ("true", "1", "yes", "sí"))

    if field == "size_kb":
        email_val = float(email.get("size_kb", 0))
        try:
            num = float(value)
        except ValueError:
            return False
        return email_val > num if operator == "gt" else email_val < num

    # Text fields
    field_map = {
        "from":    (email.get("from_addr", "") or "") + " " + (email.get("from_name", "") or ""),
        "to":      email.get("to_addr", "") or "",
        "subject": email.get("subject", "") or "",
        "body":    (email.get("body_text", "") or "") + " " + (email.get("preview", "") or ""),
    }
    email_val = field_map.get(field, "").lower()

    if operator == "contains":
        return value in email_val
    if operator == "not_contains":
        return value not in email_val
    if operator == "is":
        return email_val.strip() == value
    if operator == "starts_with":
        return email_val.startswith(value)
    if operator == "ends_with":
        return email_val.endswith(value)
    if operator == "regex":
        try:
            return bool(re.search(value, email_val))
        except re.error:
            return False
    return False


def evaluate_rules(email: dict) -> list[dict]:
    """
    Run all enabled folder rules against an email dict.
    Returns list of fired actions (may be empty).
    Stops after a rule with stop_processing=True fires.
    """
    rules = get_folder_rules()
    fired_actions = []

    for rule in rules:
        if not rule.get("enabled"):
            continue

        conditions = rule.get("conditions", [])
        logic      = rule.get("condition_logic", "AND")

        if not conditions:
            continue

        results = [_eval_condition(c, email) for c in conditions]
        matched = all(results) if logic == "AND" else any(results)

        if matched:
            increment_rule_hits(rule["id"])
            fired_actions.extend(rule.get("actions", []))
            if rule.get("stop_processing"):
                break

    return fired_actions


def apply_actions(email_id: int, actions: list[dict]) -> list[str]:
    """
    Apply a list of actions to an email by id.
    Returns a list of human-readable log strings.
    """
    from .email_db import (
        move_to_folder, mark_read, toggle_star, delete_email, get_email_by_id
    )
    log = []
    for action in actions:
        atype = action.get("type")
        aval  = action.get("value", "")

        if atype == "move":
            move_to_folder(email_id, aval)
            log.append(f"Movido a '{aval}'")
        elif atype == "copy":
            # Copy: insert a duplicate with new folder
            email = get_email_by_id(email_id)
            if email:
                from .email_db import upsert_email
                upsert_email(
                    email["account_id"], email["uid"] + "_copy", aval,
                    email["from_addr"], email["from_name"], email["to_addr"],
                    email.get("cc_addr", ""), email["subject"], email["preview"],
                    email["body_text"], email["body_html"], email["date"],
                    email["has_attachment"], email["size_kb"]
                )
            log.append(f"Copiado a '{aval}'")
        elif atype == "mark_read":
            mark_read(email_id, True)
            log.append("Marcado como leído")
        elif atype == "mark_star":
            toggle_star(email_id)
            log.append("Marcado con estrella")
        elif atype == "mark_spam":
            move_to_folder(email_id, "Spam")
            log.append("Movido a Spam")
        elif atype == "delete":
            delete_email(email_id)
            log.append("Eliminado")

    return log
