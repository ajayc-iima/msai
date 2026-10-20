"""vidhi2 rules: the judge. Five stages, fixed order, first rule fires.

Safety-A -> Scope -> Comparability -> Metadata -> Numeric.
The verdict is frozen (SHA-256) BEFORE retrieval runs.

Safety-A runs first so a prompt-injection is always refused *as* an injection
(even when it carries no survey/indicator anchor that would otherwise classify
it as out-of-scope). This is the one deliberate deviation from the v1 written
order (Scope -> Safety-A): a security backstop must precede content triage.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except Exception:  # pragma: no cover - pyyaml is a hard dependency
    yaml = None

ROOT = Path(__file__).resolve().parents[1]

CONFIDENCE_FLOOR = 0.6


@dataclass
class Verdict:
    decision: str  # PASS | WARN | REFUSE
    sub_code: str
    reason_code: str
    message: str
    stage: str
    row_id: str | None = None
    value: object = None
    unit: str | None = None
    frozen_hash: str = ""
    rule_version: str = ""
    attestation: str = ""
    citations: list[str] = field(default_factory=list)

    def freeze(self, claim, rule_version: str) -> Verdict:
        blob = json.dumps(
            {
                "claim": claim.canonical(),
                "verdict": [self.decision, self.sub_code, self.reason_code],
                "rules": rule_version,
            },
            sort_keys=True,
        )
        self.frozen_hash = hashlib.sha256(blob.encode()).hexdigest()[:16]
        self.rule_version = rule_version
        return self

    def attest(self, row: dict | None = None) -> Verdict:
        """Post-freeze figure attestation (F1 fix).

        Binds the *displayed figure* to the frozen verdict and its source cell.
        A tampered value, row_id, unit, source document or PDF changes this
        attestation even when the verdict text is unchanged. ``frozen_hash``
        proves the verdict; ``attestation`` proves the number you see is the
        number that was verified."""
        if self.value is None or self.row_id is None or not self.frozen_hash:
            self.attestation = ""
            return self
        prov = (row or {}).get("provenance", {}) or {}
        blob = json.dumps(
            {
                "frozen_hash": self.frozen_hash,
                "row_id": self.row_id,
                "value": self.value,
                "unit": self.unit,
                "source_document": (row or {}).get("source_document"),
                "pdf_sha256": prov.get("pdf_sha256"),
                "table_or_section": (row or {}).get("table_or_section"),
            },
            sort_keys=True,
            default=str,
        )
        self.attestation = hashlib.sha256(blob.encode()).hexdigest()[:16]
        return self


def _refuse(sub: str, reason: str, msg: str, stage: str) -> Verdict:
    return Verdict("REFUSE", sub, reason, msg, stage)


def _warn(sub: str, reason: str, msg: str, stage: str, **kw) -> Verdict:
    return Verdict("WARN", sub, reason, msg, stage, **kw)


class Firewall:
    def __init__(
        self,
        doc: dict | None = None,
        comparability: dict | None = None,
        truth_path: Path | None = None,
    ):
        from vidhi import store as S

        if doc is None:
            path = truth_path or (ROOT / "vidhi" / "store.json")
            try:
                doc = S.load(path)
            except Exception:
                doc = {"rows": []}
        self.doc = doc
        # Lab7: rules are data, not code. Load versioned YAML so rule_version
        # changes when caveats change. Adjudication stays hardcoded (deterministic),
        # but the frozen hash binds the exact YAML version.
        if comparability is None:
            _yp = ROOT / "data" / "vidhi" / "comparability_rules.yaml"
            if yaml is not None and _yp.exists():
                try:
                    comparability = (
                        yaml.safe_load(_yp.read_text(encoding="utf-8")) or {}
                    )
                except Exception:
                    comparability = {}
            else:
                comparability = {}
        self.rules = comparability or {}
        try:
            _rules_blob = json.dumps(self.rules, sort_keys=True, default=str)
        except Exception:
            _rules_blob = str(sorted(str(self.rules)))
        # F1: bind the verdict to the exact store content, not just its row count.
        # Any change to a row value, provenance, or the manifest changes
        # store_sha256 -> rule_version -> every frozen hash. A tampered store
        # can no longer swap a figure and keep the same "valid" hash.
        try:
            _store_blob = json.dumps(doc, sort_keys=True, default=str)
        except Exception:
            _store_blob = str(sorted(str(doc)))
        self.store_sha256 = hashlib.sha256(_store_blob.encode()).hexdigest()
        self.rule_version = hashlib.sha256(
            json.dumps(
                [_rules_blob, len(doc.get("rows", [])), self.store_sha256]
            ).encode()
        ).hexdigest()[:12]
        self._taxonomy = self._load_taxonomy()

    def _load_taxonomy(self) -> dict:
        """Load the survey taxonomy from data/vidhi/survey_metadata.yaml.

        Returns {survey_id_lower: {"indicators": {indicator_lower: {
            "measures": [...], "allowed_disaggregations": [...]}},
            "round": ...}}.
        Both in_corpus and reference_only surveys are loadable for metadata
        validation; reference_only surveys still carry store rows.
        """
        if yaml is None:
            return {}
        meta_path = ROOT / "data" / "vidhi" / "survey_metadata.yaml"
        if not meta_path.exists():
            return {}
        try:
            catalog = yaml.safe_load(meta_path.read_text(encoding="utf-8")) or {}
        except Exception:
            return {}
        out: dict = {}
        for item in catalog.get("in_corpus", []) + catalog.get("reference_only", []):
            sid = (item.get("id") or "").lower()
            inds: dict = {}
            for ind in item.get("indicators", []) or []:
                iid = (ind.get("indicator") or "").lower()
                inds[iid] = {
                    "measures": [str(m).lower() for m in (ind.get("measures") or [])],
                    "allowed_disaggregations": [
                        str(d).lower() for d in (ind.get("allowed_disaggregations") or [])
                    ],
                    "age_groups": [
                        str(a).lower() for a in (ind.get("age_groups") or [])
                    ],
                }
            out[sid] = {"indicators": inds, "round": item.get("round", "")}
        return out

    def caveat_for(self, reason_code: str, sub_code: str | None = None) -> dict | None:
        """Return the versioned YAML provenance backing a comparability rule.

        Looks the fired reason_code up in comparability_rules.yaml and returns
        {rule_id, verdict, sub_code, caveat_quote, source_doc, source_page}.
        When several rules share a reason_code (the HCES warn variant and the
        poverty-refuse variant), the entry whose sub_code matches the fired
        verdict wins. Tools (MCP) use this to surface the verbatim MoSPI
        caveat alongside the decision -- the YAML is not just a hash input,
        it is the evidence.
        """
        if not isinstance(self.rules, dict):
            return None
        matches = [
            r
            for r in (self.rules.get("rules") or [])
            if r.get("reason_code") == reason_code
        ]
        if sub_code is not None:
            matches.sort(key=lambda r: r.get("sub_code") != sub_code)
        if not matches:
            return None
        r = matches[0]
        return {
            "rule_id": r.get("rule_id"),
            "verdict": r.get("verdict"),
            "sub_code": r.get("sub_code"),
            "caveat_quote": r.get("caveat_quote"),
            "source_doc": r.get("source_doc"),
            "source_page": r.get("source_page"),
        }

    # -- stage 2: scope -------------------------------------------------
    def scope(self, c) -> Verdict | None:
        if c.wants_forecast or c.claim_type == "forecast":
            return _refuse(
                "REFUSE_SCOPE",
                "R_FORECAST",
                "Forecasts are out of scope; only published estimates are answerable.",
                "scope",
            )
        if c.wants_causal or c.claim_type == "causal":
            return _refuse(
                "REFUSE_SCOPE",
                "R_CAUSAL",
                "Causal claims are not supported by descriptive survey tables.",
                "scope",
            )
        if c.wants_political_judgment:
            return _refuse(
                "REFUSE_SCOPE",
                "R_POLITICAL",
                "Political judgments are out of scope.",
                "scope",
            )
        if c.wants_microdata or c.claim_type == "microdata":
            return _refuse(
                "REFUSE_SCOPE",
                "R_MICRODATA",
                "Individual/household microdata extraction is refused.",
                "scope",
            )
        if c.claim_type == "out_of_scope":
            return _refuse(
                "REFUSE_SCOPE",
                "R_SCOPE_OUT",
                "Question is outside the survey corpus.",
                "scope",
            )
        return None

    # -- stage 1: safety (backstop, runs before scope) --------------------
    def safety(self, c) -> Verdict | None:
        from vidhi.safety import detect_injection

        v = detect_injection(c.raw_question or "")
        if v.flagged:
            return _refuse(
                "REFUSE_SAFETY",
                "R_PROMPT_INJECTION",
                "Prompt-injection directive in the question is refused "
                f"(signals: {', '.join(v.signals)}).",
                "safety",
            )
        return None

    # -- stage 3: comparability -----------------------------------------
    def comparability(self, c) -> Verdict | None:
        ss = {str(s).lower() for s in (c.comparison_surveys or [])}
        if c.survey:
            ss.add(str(c.survey).lower())
        # ids match the extractor's vocabulary in claims.py (_SURVEYS and the
        # comparison-survey inference): nss_eus_2011_12 is produced for "EUS"
        # questions, hces_2022_23/plfs_2022_23 for explicit "2022" rounds.
        old, new = {"hces_2011_12", "nss_eus_2011_12"}, {"hces_2022_23", "hces_2023_24"}
        if ss & old and ss & new:
            if c.asserts_poverty_or_real_change:
                return _refuse(
                    "REFUSE_COMPARABILITY",
                    "R_COMPARABILITY_HCES_METHOD",
                    "Poverty/real-change inference across the 2011-12 methodology break is refused.",
                    "comparability",
                )
            return _warn(
                "WARN_COMPARABILITY",
                "R_COMPARABILITY_HCES_METHOD",
                "HCES 2011-12 vs 2022-23+ uses different instruments; level comparison needs caution.",
                "comparability",
            )
        plfs_ids = {s for s in ss if s.startswith("plfs_")}
        if "plfs_2025" in ss and plfs_ids - {"plfs_2025"}:
            return _warn(
                "WARN_COMPARABILITY",
                "R_COMPARABILITY_PLFS_REVAMP",
                "PLFS sampling was revamped from January 2025 (Jan-Dec reporting; earlier annuals Jul-Jun); do not mix series without the revamp caveat.",
                "comparability",
            )
        # Calendar rounds ("PLFS 2022/2023/2024", Jan-Dec) and traditional
        # July-June annuals are distinct survey ids in the store; a claim
        # comparing across the two series needs the reference-period caveat.
        calendar = plfs_ids & {"plfs_2022", "plfs_2023", "plfs_2024"}
        traditional = plfs_ids & {
            "plfs_2017_18", "plfs_2018_19", "plfs_2019_20",
            "plfs_2020_21", "plfs_2021_22", "plfs_2022_23", "plfs_2023_24",
        }
        if calendar and traditional:
            return _warn(
                "WARN_COMPARABILITY",
                "R_COMPARABILITY_PLFS_CALENDAR",
                "PLFS calendar rounds (Jan-Dec 2022/2023/2024) and traditional July-June annuals cover different reference periods; do not mix the series without the caveat.",
                "comparability",
            )
        if "nss_eus_2011_12" in ss and any(s.startswith("plfs") for s in ss):
            return _warn(
                "WARN_COMPARABILITY",
                "R_COMPARABILITY_EUS_PLFS",
                "Pre-PLFS EUS vs PLFS comparison requires a caveat.",
                "comparability",
            )
        if len(set(c.mixes_measures or [])) > 1 or (c.measure or "").lower() == "mixed":
            return _warn(
                "WARN_COMPARABILITY",
                "R_COMPARABILITY_STATUS_MIX",
                "Usual-status and CWS figures measure different reference periods; do not mix.",
                "comparability",
            )
        return None

    # -- stage 4: metadata ----------------------------------------------
    def metadata(self, c) -> Verdict | None:
        """Validate claim dimensions against the survey taxonomy.

        Fires AFTER comparability (which handles cross-round breaks) and
        BEFORE numeric. Unknown survey / indicator / measure / unsupported
        disaggregation emits a WARN with a named reason code. Round
        compatibility is intentionally NOT checked here: it is enforced by
        the strict store lookup (no row for that round -> WARN_NO_DATA).
        Definitional claims skip metadata entirely.
        """
        if c.claim_type == "definitional":
            return None
        tax = self._taxonomy
        sid = (c.survey or "").lower()
        if not sid:
            return _warn(
                "WARN_METADATA",
                "R_METADATA_UNKNOWN_SURVEY",
                "Survey not specified; cannot validate against the taxonomy.",
                "metadata",
            )
        if sid not in tax:
            return _warn(
                "WARN_METADATA",
                "R_METADATA_UNKNOWN_SURVEY",
                f"Survey {c.survey} is not in the metadata catalog.",
                "metadata",
            )
        entry = tax[sid]
        inds = entry.get("indicators", {})
        iid = (c.indicator or "").lower()
        if not iid:
            return _warn(
                "WARN_METADATA",
                "R_METADATA_UNKNOWN_INDICATOR",
                "Indicator not specified; cannot validate disaggregations.",
                "metadata",
            )
        if iid not in inds:
            return _warn(
                "WARN_METADATA",
                "R_METADATA_UNKNOWN_INDICATOR",
                f"Indicator {c.indicator} is not defined for {c.survey}.",
                "metadata",
            )
        ind = inds[iid]
        # Measure check (mixed measure is handled by Comparability).
        if c.measure:
            cm = c.measure.lower()
            if cm not in ind.get("measures", []) and cm != "mixed":
                return _warn(
                    "WARN_METADATA",
                    "R_METADATA_UNSUPPORTED_MEASURE",
                    f"Measure {c.measure} is not defined for {c.indicator} in {c.survey}.",
                    "metadata",
                )
        # Disaggregation checks against allowed_disaggregations.
        allowed = set(ind.get("allowed_disaggregations", []))
        dim_checks = [
            ("sex", c.sex),
            ("residence", c.residence),
            ("state", c.state),
            ("activity", c.activity),
        ]
        for dim, val in dim_checks:
            if val and str(val).lower() not in ("all", "mixed") and dim not in allowed:
                return _warn(
                    "WARN_METADATA",
                    "R_METADATA_UNSUPPORTED_DISAGGREGATION",
                    f"Disaggregation {dim}={val} is not supported for "
                    f"{c.indicator} in {c.survey}.",
                    "metadata",
                )
        if c.age_group and str(c.age_group).lower() not in ("all", "mixed"):
            # Taxonomy lists the age buckets each survey's indicators carry
            # (age_groups); fall back to the legacy age_group_15plus key.
            allowed_ages = set(ind.get("age_groups", []))
            if not allowed_ages and "age_group_15plus" in allowed:
                allowed_ages = {"15plus"}
            if str(c.age_group).lower() not in allowed_ages:
                return _warn(
                    "WARN_METADATA",
                    "R_METADATA_UNSUPPORTED_DISAGGREGATION",
                    f"Disaggregation age_group={c.age_group} is not supported for "
                    f"{c.indicator} in {c.survey}.",
                    "metadata",
                )
        return None

    # -- stage 5: numeric (confidence gate embedded inside) ----
    def _split(self, c) -> Verdict | None:
        """Same-survey split comparison (rural vs urban, male vs female):
        answer every verified side, cite each row."""
        from vidhi import store as S

        q = (c.raw_question or "").lower()
        dims = []
        if "rural" in q and "urban" in q:
            dims.append(("residence", ["rural", "urban"]))
        if re.search(r"\bmale\b", q) and re.search(r"\bfemale\b", q):
            dims.append(("sex", ["male", "female"]))
        if not dims:
            return None
        for dim, vals in dims:
            got = []
            for v in vals:
                row = S.lookup(self.doc, c.model_copy(update={dim: v}))
                if row is None:
                    break
                got.append((v, row))
            if len(got) == len(vals):
                # "cite each row" (docstring): every side carries its source
                # row id, not just the last-looked-up one.
                figs = "; ".join(
                    f"{v} {r['value']} {(r.get('unit') or '').strip()}".strip()
                    + f" (row {r['row_id']})"
                    for v, r in got
                )
                return Verdict(
                    "PASS",
                    "PASS_WITH_NUMBER",
                    "R_OK",
                    f"Official figures ({c.round or ''}): {figs}.",
                    "numeric",
                    got[-1][1]["row_id"],
                    None,
                    got[-1][1].get("unit"),
                )
        return None

    def _pairs(self, c) -> Verdict:
        from vidhi import store as S

        checked = []
        for p in c.asserted_pairs:
            row = S.lookup(self.doc, c.model_copy(update={"round": str(p["round"])}))
            if row is None:
                return _warn(
                    "WARN_NO_DATA",
                    "R_NO_CURATED_ROW",
                    f"No curated row for {c.indicator} in round "
                    f"{p['round']}; no figure endorsed.",
                    "numeric",
                )
            try:
                match = abs(float(p["value"]) - float(row["value"])) <= 1e-9
            except (TypeError, ValueError):
                match = False
            if not match:
                return _warn(
                    "WARN_NUMERIC_MISMATCH",
                    "R_NUMERIC_MISMATCH",
                    f"Figure {p['value']} for round {p['round']} "
                    f"disagrees with official {row['value']} "
                    f"{row.get('unit')}.",
                    "numeric",
                    row_id=row["row_id"],
                    value=row["value"],
                    unit=row.get("unit"),
                )
            checked.append((p, row))
        if not checked:
            return _warn(
                "WARN_NO_DATA",
                "R_NO_CURATED_ROW",
                "No asserted numeric pairs to check; no figure endorsed.",
                "numeric",
            )
        (new_p, new_r) = checked[-1]
        return Verdict(
            "PASS",
            "PASS_WITH_NUMBER",
            "R_OK",
            "Asserted figures match official tables.",
            "numeric",
            new_r["row_id"],
            new_p["value"],
            new_r.get("unit"),
        )

    _numeric_pairs = _pairs

    def numeric(self, c) -> Verdict:
        from vidhi import store as S

        if c.claim_type == "definitional":
            return Verdict(
                "PASS",
                "PASS_METHODOLOGY_ONLY",
                "R_OK",
                "Methodology question answered from official excerpts.",
                "numeric",
            )
        if c.asserted_pairs:
            return self._pairs(c)
        if c.claim_type == "comparative" and c.user_asserted_value is None:
            split = self._split(c)
            if split is not None:
                return split
        row = S.lookup(self.doc, c)
        if row is None:
            return _warn(
                "WARN_NO_DATA",
                "R_NO_CURATED_ROW",
                "Valid question but no curated numeric row; no figure given.",
                "numeric",
            )
        if c.user_asserted_value is not None:
            try:
                if abs(float(c.user_asserted_value) - float(row["value"])) <= 1e-9:
                    return Verdict(
                        "PASS",
                        "PASS_WITH_NUMBER",
                        "R_OK",
                        "User figure matches the official table.",
                        "numeric",
                        row["row_id"],
                        row["value"],
                        row.get("unit"),
                    )
            except (TypeError, ValueError):
                pass
            return _warn(
                "WARN_NUMERIC_MISMATCH",
                "R_NUMERIC_MISMATCH",
                f"User figure {c.user_asserted_value} disagrees with official "
                f"{row['value']} {row.get('unit')}.",
                "numeric",
                row_id=row["row_id"],
                value=row["value"],
                unit=row.get("unit"),
            )
        return Verdict(
            "PASS",
            "PASS_WITH_NUMBER",
            "R_OK",
            "Official figure retrieved.",
            "numeric",
            row["row_id"],
            row["value"],
            row.get("unit"),
        )

    def adjudicate(self, c) -> Verdict:
        for stage in (self.safety, self.scope, self.comparability, self.metadata):
            v = stage(c)
            if v is not None:
                return v.freeze(c, self.rule_version)
        if (
            c.extraction_confidence < CONFIDENCE_FLOOR
            and c.claim_type != "definitional"
        ):
            v = self.numeric(c)
            if v.decision == "PASS":
                return _warn(
                    "WARN_LOW_CONFIDENCE",
                    "R_LOW_EXTRACTION_CONF",
                    "Low extraction confidence; will not silently PASS.",
                    "confidence",
                ).freeze(c, self.rule_version)
            return v.freeze(c, self.rule_version)
        return self.numeric(c).freeze(c, self.rule_version)
