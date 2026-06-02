"""
Spam filter engine.

Uses three layers:
1. Whitelist  – always inbox
2. Blacklist  – sender / domain / keyword rules stored in DB
3. Heuristic  – pattern scoring (ALL CAPS ratio, special chars, etc.)
"""
import re
import math
from collections import Counter
from .email_db import (
    get_spam_rules, increment_spam_hits, add_spam_rule
)

# ── Heuristic patterns ────────────────────────────────────────
SPAM_PATTERNS = [
    (r"\bv[i1]agra\b",           3),
    (r"\bcasino\b",               2),
    (r"\blotter[y|ie]\b",         3),
    (r"\bwin\s+(a\s+)?prize\b",   3),
    (r"\b(click\s+here|act\s+now|limited\s+time)\b", 2),
    (r"\b(free\s+gift|free\s+money|free\s+offer)\b",  3),
    (r"\b(make\s+money\s+fast|earn\s+cash)\b",         3),
    (r"\bunsubscribe\b",          1),
    (r"http[s]?://[^\s]+\b",      0.5),   # any link adds a small score
    (r"\$\d+",                    0.5),
    (r"!!!+",                     1),
    (r"\?\?\?+",                  1),
]

SPAM_THRESHOLD = 5.0   # score ≥ this → spam


# ── Naive-Bayes word model (in-memory, built from DB rules) ──

class _NaiveBayes:
    """Minimal bag-of-words Naive Bayes for spam detection."""

    def __init__(self):
        self.spam_words:   Counter = Counter()
        self.ham_words:    Counter = Counter()
        self.spam_total:   int = 0
        self.ham_total:    int = 0

    def _tokenize(self, text: str):
        return re.findall(r"[a-z]{3,}", text.lower())

    def train(self, text: str, is_spam: bool):
        tokens = self._tokenize(text)
        if is_spam:
            self.spam_words.update(tokens)
            self.spam_total += len(tokens)
        else:
            self.ham_words.update(tokens)
            self.ham_total += len(tokens)

    def score(self, text: str) -> float:
        """Return log-odds ratio (positive = more spam-like)."""
        if not self.spam_total or not self.ham_total:
            return 0.0
        tokens = self._tokenize(text)
        log_odds = 0.0
        vocab = len(set(list(self.spam_words) + list(self.ham_words)))
        for tok in tokens:
            p_spam = (self.spam_words.get(tok, 0) + 1) / (self.spam_total + vocab)
            p_ham  = (self.ham_words.get(tok,  0) + 1) / (self.ham_total  + vocab)
            log_odds += math.log(p_spam / p_ham)
        return log_odds


_bayes = _NaiveBayes()


def _heuristic_score(subject: str, body: str) -> float:
    text = f"{subject} {body}".lower()
    score = 0.0
    for pat, weight in SPAM_PATTERNS:
        hits = len(re.findall(pat, text, re.IGNORECASE))
        score += hits * weight
    # ALL-CAPS ratio
    letters = re.findall(r"[a-zA-Z]", text)
    if letters:
        caps_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
        if caps_ratio > 0.5:
            score += 2.0
    return score


def check_email(from_addr: str, subject: str, body: str) -> dict:
    """
    Returns:
        {
          'is_spam': bool,
          'score': float,
          'reasons': [str],
          'action': 'spam'|'delete'|'inbox'
        }
    """
    from_addr_lower = (from_addr or "").lower()
    subject_lower   = (subject  or "").lower()
    body_lower      = (body     or "").lower()

    reasons = []
    total_score = 0.0
    action = "inbox"

    rules = get_spam_rules()

    for rule in rules:
        if not rule["enabled"]:
            continue
        val = rule["value"]
        rtype = rule["rule_type"]

        matched = False
        if rtype == "whitelist_sender" and (val in from_addr_lower):
            return {"is_spam": False, "score": 0.0,
                    "reasons": [f"Whitelist: {val}"], "action": "inbox"}
        elif rtype == "sender" and (val in from_addr_lower):
            matched = True
            total_score += 10
            reasons.append(f"Remitente bloqueado: {val}")
        elif rtype == "domain" and from_addr_lower.endswith(f"@{val}"):
            matched = True
            total_score += 10
            reasons.append(f"Dominio bloqueado: {val}")
        elif rtype == "keyword_subject" and val in subject_lower:
            matched = True
            total_score += 5
            reasons.append(f"Asunto contiene: {val}")
        elif rtype == "keyword_body" and val in body_lower:
            matched = True
            total_score += 3
            reasons.append(f"Cuerpo contiene: {val}")

        if matched:
            increment_spam_hits(rule["id"])
            action = rule["action"]
            if action in ("spam", "delete"):
                return {
                    "is_spam": True,
                    "score": total_score,
                    "reasons": reasons,
                    "action": action,
                }

    # Heuristic scoring
    h_score = _heuristic_score(subject, body)
    total_score += h_score
    if h_score > 2:
        reasons.append(f"Heurística spam (score={h_score:.1f})")

    # Bayesian
    b_score = _bayes.score(f"{subject} {body}")
    if b_score > 2:
        total_score += b_score
        reasons.append(f"Bayesiano spam (log-odds={b_score:.1f})")

    is_spam = total_score >= SPAM_THRESHOLD
    if is_spam and action == "inbox":
        action = "spam"

    return {
        "is_spam": is_spam,
        "score": round(total_score, 2),
        "reasons": reasons,
        "action": action,
    }


def train_spam(text: str, is_spam: bool):
    _bayes.train(text, is_spam)


# ── Default rules seed (called once) ─────────────────────────

DEFAULT_SPAM_KEYWORDS_SUBJECT = [
    "winner", "congratulations", "you have won", "click here",
    "free money", "act now", "limited time offer", "verify your account",
    "account suspended", "password expired",
]
DEFAULT_SPAM_KEYWORDS_BODY = [
    "unsubscribe", "opt-out", "this is not spam",
]
DEFAULT_BLOCKED_DOMAINS = [
    "0-mail.com", "10minutemail.com", "guerrillamail.com",
    "mailinator.com", "throwam.com", "tempmail.com",
]


def seed_default_rules():
    for kw in DEFAULT_SPAM_KEYWORDS_SUBJECT:
        add_spam_rule("keyword_subject", kw, "spam")
    for kw in DEFAULT_SPAM_KEYWORDS_BODY:
        add_spam_rule("keyword_body", kw, "spam")
    for dom in DEFAULT_BLOCKED_DOMAINS:
        add_spam_rule("domain", dom, "spam")
