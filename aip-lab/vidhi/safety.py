# ruff: noqa: BLE001 - guarded fallbacks are intentional (offline/portable paths)
"""vidhi safety: self-contained Safety-A prompt-injection detection.

A transparent, deterministic regex baseline (auditable, reason-coded), extended
with Hindi (Devanagari) and Hinglish (Roman-script) signals for the Indian user
base. A measured open-weights classifier (e.g. Prompt Guard 2's 86M multilingual
mDeBERTa, or a distilled MuRIL student) can be layered on top behind
``VIDHI_SAFETY_MODE``, but the baseline must stay deterministic and
reason-coded so the freeze-before-retrieval guarantee is never weakened.

This module deliberately does NOT import from ``aip.guards`` so the firewall
stays portable toward the independence mandate. ``rules.py`` blocks on *any*
signal, not only ``override`` (the v1 defect where 5 of 6 signals were computed
and then ignored).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

# (signal_name, compiled pattern). Order matters only for reporting; every
# signal that matches is recorded so the refusal message can name the class.
# Signals target the assistant's *own* configuration (system prompt, keys),
# not merely suspicious-looking words: "show the survey instructions" and
# "batao ... key findings" are legitimate and must not be refused.
_SIGNALS: list[tuple[str, re.Pattern]] = [
    # --- English (parity with the audit baseline) -------------------------
    ("override", re.compile(
        r"ignore (?:all |any |the )?(?:previous|prior|above)\s+"
        r"(?:instructions?|prompts?|rules?)", re.I)),
    ("role_switch", re.compile(
        r"\byou are now\b|\bnew system prompt\b|\bact as if\b", re.I)),
    ("exfiltration", re.compile(
        r"\b(?:reveal|print|repeat|show|output|dump|leak)\b.{0,40}"
        r"\b(?:system prompt|(?:your|hidden|original|initial|internal|system)\s+"
        r"(?:system\s+)?instructions?|api[_ ]?key|secret[_ ]?key|"
        r"access[_ ]?token|password)\b", re.I)),
    ("delimiter_break", re.compile(
        r"</?(?:system|instructions?|context|untrusted)>|```\s*system", re.I)),
    ("tool_coercion", re.compile(
        r"\b(?:call|invoke|use)\b.{0,30}\btool\b.{0,60}"
        r"\b(?:delete|transfer|send|email|drop|refund)\b", re.I)),
    ("encoded", re.compile(
        r"[A-Za-z0-9+/]{40,}={0,2}[()\s]*\s*(?:decode|base64|encoded|decrypt)", re.I)),
    # --- Hindi / Devanagari -------------------------------------------------
    ("hindi_override", re.compile(
        r"(?:पिछले|पिछली|पूर्व|ऊपर|उपरोक्त).{0,40}"
        r"(?:निर्देश|निर्देशों|प्रॉम्प्ट|आदेश|नियम).{0,25}"
        r"(?:अनदेखा|नज़रअंदाज़|नज़रअंदाज|भूल|छोड़|मत\s*मान|अनदेखी)", re.I)),
    ("hindi_role_switch", re.compile(
        r"(?:तुम|आप).{0,30}अब.{0,20}(?:हो|बन|बन\s*गए)"
        r"|नया.{0,15}(?:सिस्टम|प्रॉम्प्ट|निर्देश)", re.I)),
    ("hindi_exfiltration", re.compile(
        r"(?:बताओ|बताइए|बताना|दिखाओ|दिखाइए|प्रकट|प्रिंट|लिखो|बता).{0,40}"
        r"(?:सिस्टम\s*प्रॉम्प्ट|प्रॉम्प्ट|अपन[ेा]\s+निर्देश|कुंजी|सीक्रेट|"
        r"टोकन|पासवर्ड)", re.I)),
    # --- Hinglish (Roman-script Hindi) -------------------------------------
    ("hinglish_override", re.compile(
        r"(?:ignore|bhool|hata|chhodo|mat\s*mano).{0,25}"
        r"(?:sab|pichhle|pehle|previous|upar\s*wale).{0,20}"
        r"(?:instructions|nirdesh|prompt|rules|aadesh)", re.I)),
    ("hinglish_exfiltration", re.compile(
        r"(?:batao|bata|dikhao|print\s*karo|show\s*karo).{0,40}"
        r"(?:system\s*prompt|prompt|nirdesh|api\s*key|secret\s*key|"
        r"password|access\s*token)", re.I)),
]


@dataclass
class InjectionVerdict:
    flagged: bool
    signals: list[str] = field(default_factory=list)
    detail: dict[str, str] = field(default_factory=dict)


# Zero-width / invisible codepoints commonly used to evade regex filters
# (see the 2025 "invisible-font prompt in academic papers" incident).
_ZERO_WIDTH = "\u200b\u200c\u200d\u200e\u200f\u2060\u2061\u2062\u2063\u2064\ufeff\u00ad\u034f\u061c"


def _normalize(text: str) -> str:
    """NFKC-normalize and strip zero-width/invisible characters so that
    Unicode-hidden injections (invisible-font text, full-width homoglyphs) are
    caught by the plain-text signal patterns."""
    t = unicodedata.normalize("NFKC", text or "")
    for ch in _ZERO_WIDTH:
        t = t.replace(ch, "")
    return t


def detect_injection(text: str) -> InjectionVerdict:
    """Deterministic multilingual injection detection.

    Returns every matching signal class (English, Hindi, Hinglish) so the
    firewall can (a) refuse on any hit and (b) tell the user *why*.
    """
    text = _normalize(text)
    hits: list[str] = []
    detail: dict[str, str] = {}
    for name, pat in _SIGNALS:
        m = pat.search(text or "")
        if m:
            hits.append(name)
            detail[name] = m.group()[:120]
    return InjectionVerdict(bool(hits), hits, detail)
