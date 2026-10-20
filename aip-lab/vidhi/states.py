"""Canonical state/UT vocabulary — one source of truth for the whole app.

The store prints state/UT names in MoSPI's spelling (the key of
:data:`CANON`). Real questions use many other spellings: "mpce in mp",
"mpce in up", "m.p.", "orissa", "pondicherry", "j&k", "maharastra".
This module maps every accepted spelling to the canonical store name, so
the claim translator, the consistency checker and the tests all agree.

Design rules
------------
* **Canonical names are the store's**, never a guess: `tests/` asserts that
  every canonical name here exists in `vidhi/store.json` and that every
  state in the store is reachable through an alias. Adding a state to the
  store without an alias fails the test suite instead of silently
  answering "no data".
* **Full names and long variants always match** on whole-word boundaries
  ("orissa" -> Odisha, "j&k" -> Jammu & Kashmir).
* **Short codes need geographic context** ("in mp", "for up", "mp and up")
  or a list slot ("Madhya Pradesh, mp, up"). A bare "up" in ordinary prose
  is not a state.
* **Long names tolerate a typo** ("maharastra" -> Maharashtra): one edit
  for names of eight characters or more, so "punjabi" never becomes
  "Punjab" and "goal" never becomes "Goa".
"""

from __future__ import annotations

import difflib
import re

# Canonical store name -> accepted spellings (lowercase, punctuation-free).
CANON: dict[str, tuple[str, ...]] = {
    "Andaman & Nicobar Islands": (
        "andaman and nicobar islands",
        "andaman nicobar islands",
        "andaman nicobar",
        "anp",
    ),
    "Andhra Pradesh": ("andhra pradesh", "ap"),
    "Arunachal Pradesh": ("arunachal pradesh", "arunachal"),
    "Assam": ("assam", "asm"),
    "Bihar": ("bihar", "br"),
    "Chandigarh": ("chandigarh", "ch"),
    "Chhattisgarh": ("chhattisgarh", "chhattisgarh", "cg"),
    "Dadra & Nagar Haveli and Daman & Diu": (
        "dadra and nagar haveli and daman and diu",
        "dadra nagar haveli and daman and diu",
        "dadra nagar haveli daman diu",
        "dadra and daman and diu",
        "dadra nagar haveli",
        "dnh",
    ),
    "Delhi": ("delhi", "new delhi", "nct of delhi", "dl"),
    "Goa": ("goa",),
    "Gujarat": ("gujarat", "gj"),
    "Haryana": ("haryana", "hr"),
    "Himachal Pradesh": ("himachal pradesh", "himachal", "hp"),
    "Jammu & Kashmir": (
        "jammu and kashmir",
        "jammu kashmir",
        "j k",
        "jk",
    ),
    "Jharkhand": ("jharkhand", "jh"),
    "Karnataka": ("karnataka", "ka"),
    "Kerala": ("kerala", "kl"),
    "Ladakh": ("ladakh",),
    "Lakshadweep": ("lakshadweep", "lakshadweep islands"),
    "Madhya Pradesh": ("madhya pradesh", "mp", "m p"),
    "Maharashtra": ("maharashtra", "mh", "m h"),
    "Manipur": ("manipur", "mn"),
    "Meghalaya": ("meghalaya", "ml"),
    "Mizoram": ("mizoram", "mz"),
    "Nagaland": ("nagaland", "nl"),
    "Odisha": ("odisha", "orissa", "od"),
    "Puducherry": ("puducherry", "pondicherry", "py"),
    "Punjab": ("punjab", "pb"),
    "Rajasthan": ("rajasthan", "rj"),
    "Sikkim": ("sikkim", "sk"),
    "Tamil Nadu": ("tamil nadu", "tamilnadu", "tn", "t n"),
    "Telangana": ("telangana", "ts"),
    "Tripura": ("tripura", "tr"),
    "Uttar Pradesh": ("uttar pradesh", "up", "u p"),
    "Uttarakhand": ("uttarakhand", "uk", "u k"),
    "West Bengal": ("west bengal", "wb", "w b"),
}

# A short code is only a state when the question places it in a geographic
# slot ("in mp", "for up", "mp and up") or in a list of places.
_CONTEXT_BEFORE = {"in", "at", "of", "for", "state", "and", "or"}
_CONTEXT_AFTER = {"state", "pradesh"}

# Words that make a two-letter code ambiguous ("uk" = United Kingdom).
_NEGATIVE = {"united kingdom", "britain", "english", "uk government"}

# Typo tolerance: only for long names, one edit (transposition counts).
_FUZZY_MIN_LEN = 8
_FUZZY_MAX_EDITS = 1


def normalize(text: str) -> str:
    """Lowercase, drop punctuation, collapse whitespace."""
    q = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return " ".join(q.split())


def _is_code(alias: str) -> bool:
    """Short codes (one to three letters, or dotted forms) need context."""
    return len(alias.replace(" ", "")) <= 3


def _alias_index() -> list[tuple[str, str, bool]]:
    idx: list[tuple[str, str, bool]] = []
    for canon, aliases in CANON.items():
        for alias in aliases:
            idx.append((normalize(alias), canon, _is_code(alias)))
    # Longest alias first: "madhya pradesh" must win over "mp", and
    # "andhra pradesh" over a hypothetical "andhra".
    idx.sort(key=lambda t: (-len(t[0].split()), -len(t[0])))
    return idx


_ALIAS_INDEX = _alias_index()
_CODE_INDEX = [(a, c) for a, c, is_code in _ALIAS_INDEX if is_code]
_NAME_INDEX = [(a, c) for a, c, is_code in _ALIAS_INDEX if not is_code]


def _segments(question: str) -> list[str]:
    """Comma/colon/semicolon-delimited chunks of the question."""
    raw = re.sub(r"[;:,()\[\]?]", "|", question.lower())
    return [s.strip() for s in raw.split("|") if s.strip()]


def _alias_pattern(alias: str) -> re.Pattern:
    """Punctuation-insensitive, word-bounded pattern for an alias.

    "m p" also matches "m.p." and "m-p"; "andaman nicobar islands" matches
    "andaman & nicobar islands".
    """
    parts = alias.split()
    body = r"[^a-z0-9]{0,3}".join(re.escape(p) for p in parts)
    return re.compile(rf"(?<![a-z0-9]){body}(?![a-z0-9])", re.IGNORECASE)


_PATTERN_INDEX = [(a, c, _alias_pattern(a)) for a, c, _ in _ALIAS_INDEX]


def _damerau(a: str, b: str, limit: int) -> int:
    """Damerau-Levenshtein distance, capped at `limit` (cheap early exit)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev2: list[int] = []
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            val = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            if (
                i > 1
                and j > 1
                and ca == b[j - 2]
                and a[i - 2] == cb
                and cost
            ):
                val = min(val, prev2[j - 2] + 1)
            cur[j] = val
        if min(cur) > limit:
            return limit + 1
        prev2, prev = prev, cur
    return prev[-1]


def _fuzzy_names(text: str) -> list[tuple[int, str]]:
    """Long state names with a single typo ("maharastra" -> Maharashtra)."""
    hits: list[tuple[int, str]] = []
    for name, canon in _NAME_INDEX:
        if len(name) < _FUZZY_MIN_LEN:
            continue
        n = len(name.split())
        toks = list(re.finditer(r"[a-z0-9]+", text.lower()))
        for i in range(len(toks) - n + 1):
            cand = " ".join(t.group(0) for t in toks[i : i + n])
            if cand == name:
                break  # exact match already handled
            if _damerau(cand, name, _FUZZY_MAX_EDITS) <= _FUZZY_MAX_EDITS:
                hits.append((toks[i].start(), canon))
                break
    return hits


def match_state(question: str) -> str | None:
    """Return the canonical store name for the state named in `question`.

    `None` when the question names no state (the caller then treats the
    claim as national).
    """
    found = match_states(question)
    return found[0] if found else None


def match_states(question: str) -> list[str]:
    """Every state named in `question`, in order of first appearance.

    A question may name several ("MPCE in Madhya Pradesh, UP, Maharashtra");
    the caller must then answer each of them instead of picking one.
    """
    text = question or ""
    low = text.lower()
    if not normalize(low) or any(neg in low for neg in _NEGATIVE):
        return []

    hits: list[tuple[int, str]] = []
    # 1) full names and long aliases, anywhere in the text
    for alias, canon, pat in _PATTERN_INDEX:
        if _is_code(alias):
            continue
        m = pat.search(text)
        if m:
            hits.append((m.start(), canon))
    # 2) long names with a typo
    hits.extend(_fuzzy_names(text))

    # 3) short codes: a geographic slot ("in mp", "mp and up") ...
    code_hits: list[tuple[int, str]] = []
    for alias, canon, pat in _PATTERN_INDEX:
        if not _is_code(alias):
            continue
        for m in pat.finditer(text):
            before = re.search(r"([a-z]+)\s*$", low[: m.start()])
            after = re.match(r"\s*([a-z]+)", low[m.end() :])
            prev_word = before.group(1) if before else ""
            next_word = after.group(1) if after else ""
            in_slot = prev_word in _CONTEXT_BEFORE or next_word in _CONTEXT_AFTER
            listed = bool(re.search(r"[,;:(\[]\s*$", low[: m.start()]))
            if in_slot:
                code_hits.append((m.start(), canon))
                break
            if listed:
                code_hits.append((m.start(), canon, "pending"))  # type: ignore
                break
    # A bare code in a list counts only when the question names a state
    # outright or another code in a geographic slot.
    named = {c for _, c in hits}
    settled: list[tuple[int, str]] = []
    pending: list[tuple[int, str]] = []
    for h in code_hits:
        if len(h) == 2:
            settled.append(h)
        else:
            pending.append((h[0], h[1]))
    if named or settled:
        settled.extend(pending)
    hits.extend(settled)

    hits.sort()
    out: list[str] = []
    for _, canon in hits:
        if canon not in out:
            out.append(canon)
    return out


def canonical_names() -> list[str]:
    """Canonical store names (the keys of :data:`CANON`)."""
    return list(CANON)


def lower_names() -> list[str]:
    """Lowercase canonical names, for text proximity checks."""
    return [c.lower() for c in CANON]


# Capitalised words that are never a place: survey programme names, month
# names and common non-place nouns. Anything else in a geographic slot
# ("in X", "for X") is an unknown geography -- the firewall must abstain
# rather than answer with another geography's figures.
_NOT_A_PLACE = {
    "hces", "plfs", "tus", "mis", "nss", "nso", "mospi", "nsfi", "ai",
    "rs", "inr", "rupees", "india", "all", "the", "state", "states", "and",
    "of", "for", "in", "at", "from", "nation", "country", "every", "each",
    "january", "february", "march", "april", "may", "june", "july", "august",
    "september", "october", "november", "december", "quarter", "year",
    "rural", "urban", "male", "female", "males", "females", "person",
    "persons", "total", "overall", "average", "labour", "force", "consumption",
    "expenditure", "time", "use", "survey", "round", "report", "factsheet",
    "annual", "current", "weekly", "status", "usual", "per", "capita",
    "monthly", "implicit", "explicit", "imputed", "values", "value", "free",
    "items", "item", "with", "without", "mpce", "lfpr", "wpr", "ur", "cws",
    "magnitude", "growth", "rate", "level", "levels",
}

# A geographic slot: "in Bihar", "for Kerala", "from Goa".
_GEO_SLOT = re.compile(
    r"\b(?:in|for|at|from)\s+"
    r"((?:[A-Z][A-Za-z.&'-]*)(?:\s+(?:and|of|the)?\s*[A-Z][A-Za-z.&'-]*){0,2})"
)

_KNOWN_PHRASES = {
    normalize(a) for a, _, _ in _ALIAS_INDEX
} | {normalize(c) for c in CANON}

_KNOWN_WORDS = {w for phrase in _KNOWN_PHRASES for w in phrase.split()}


def known_place(phrase: str) -> bool:
    """True when the phrase names a state/UT the store curates (or is not a
    place at all)."""
    p = normalize(phrase)
    if not p:
        return True
    if p in _KNOWN_PHRASES:
        return True
    words = [w for w in p.split() if w not in ("and", "of", "the")]
    if not words:
        return True
    return all(w in _KNOWN_WORDS or w in _NOT_A_PLACE for w in words)


def unknown_places(question: str) -> list[str]:
    """Place-like words in a geographic slot that the store does not cover.

    "MPCE in Atlantis" -> ["Atlantis"]: the question is about a place we
    have no rows for, so the firewall must abstain instead of quietly
    answering with the all-India figures.
    """
    out: list[str] = []
    for m in _GEO_SLOT.finditer(question or ""):
        phrase = m.group(1)
        if known_place(phrase):
            continue
        for word in re.split(r"[\s,.;:]+", phrase):
            w = word.strip(".,;:'\"")
            if not w or known_place(w):
                continue
            if w.lower() in _NOT_A_PLACE:
                continue
            if w.lower() in _KNOWN_WORDS:
                continue
            if w not in out:
                out.append(w)
    return out
def suggest_state(name: str) -> str | None:
    """Closest curated state/UT name for a possibly-misspelled place, or None.

    Used to make an honest abstention *helpful*: "MPCE in Atlantis" still
    returns WARN_NO_DATA (never a figure), but the note can add
    "Did you mean '...'?" when the token is plausibly a typo of a curated
    state. Returns None for known places, short tokens and anything too far
    from every curated name, so we never invent a suggestion.
    """
    if not name:
        return None
    if known_place(name):
        return None
    low = normalize(name)
    if not low or len(low) < 4:
        return None
    cands: list[tuple[str, str]] = []
    seen_keys: set[str] = set()
    for canon, aliases in CANON.items():
        for src in (canon,) + tuple(aliases):
            if len(src) < 5:
                continue
            key = normalize(src).replace(" ", "")
            if key in seen_keys:
                continue
            seen_keys.add(key)
            cands.append((canon, key))
    q = low.replace(" ", "")
    best_canon: str | None = None
    best_ratio = 0.0
    for canon, key in cands:
        r = difflib.SequenceMatcher(None, q, key).ratio()
        if r > best_ratio:
            best_ratio = r
            best_canon = canon
    if best_canon is None or best_ratio < 0.72:
        return None
    return best_canon


def suggest_states(question: str) -> list[str]:
    """Suggestions (one per unknown place) for a question, in order."""
    out: list[str] = []
    for place in unknown_places(question or ""):
        s = suggest_state(place)
        if s and s not in out:
            out.append(s)
    return out
