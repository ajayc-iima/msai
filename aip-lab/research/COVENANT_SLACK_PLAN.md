# Project SLACK — Realized Covenant Slack from EDGAR Contract Text
**Status:** Pre-pilot plan · 2026-10-05 · Author: Ajay Choudhary (MSAI, Plaksha)
**Target collaboration:** ISB Accounting (G. Sandhu — credit markets; K. Balakrishnan — information problems, TAR editor)

---

## 0. Evidence status (read this first)

**VERIFIED this session (OpenAlex, 2026-10-05):**
- Li, Neamtiu, Tu (TAR 2024), "Do Firms Withhold Loan Covenant Details?" doi:10.2308/tar-2020-0445. Abstract states: *"the precise covenant details of many loans are not publicly available."* → the gap we fill. They study disclosure choice; we build the missing measure.
- Ivashina & Vallée, "Weak Credit Covenants" (NBER WP 2020). Measures covenant *terms* weakness, not realized slack.
- Chodorow-Reich & Falato (JF 2021), "The Loan Covenant Channel." Violation → real effects; uses standard violation proxies.
- Bouwens, de Kok, Verriest (2019), EBITDA validity in contracts. Note: de Kok is also co-author of TAR 2026 GPT-complexity — adjacent, watch his pipeline.
- Batta & Badawi (SSRN 2026), "Defensive Contract Language." Contract-NLP, adjacent.
- No paper found (searches 2018-2026, 4 query families) that extracts covenant *formulas* from EDGAR exhibits and recomputes realized slack. Gap appears open. **This is a search result, not a guarantee — SSRN must be hand-checked before submission.**

**ASSUMED — verify on Day 1 (each is a checkbox):**
- [ ] WRDS seat includes LSEG DealScan tables, incl. the **financial covenant module** (type + initial level).
- [ ] WRDS seat includes **LSEG Loan Connector** with vintage covering ≥2015 (older vintages of the Roberts link end ~2020 or earlier).
- [ ] DealScan facility ↔ EDGAR exhibit match is feasible at ≥60% for public borrowers (fuzzy: GVKEY borrower name + signing date ±30d + amount ±20%).
- [ ] EDGAR full-text search API (efts.sec.gov) returns exhibit text for 2010+ credit agreements; rate limit 10 req/s with declared User-Agent.
- [ ] No redistribution constraint violated: we store filing IDs, offsets, and hashes — not full contract text.

---

## 1. One-line pitch

> For 30 years covenant slack has been *estimated* from DealScan summaries. We measure it *directly*: an agent extracts covenant formulas — including the defined-term chains and bespoke EBITDA addbacks — from the actual credit agreements filed as EDGAR exhibits, and recomputes slack each quarter against XBRL financials.

**Construct:** `slack_{i,c,q}` = (actual metric − threshold) / |threshold|, per covenant c, firm i, quarter q, with the metric computed **per the contract's own definition** (not GAAP, not Compustat's EBITDA).

**Second construct (free byproduct):** `addback_index_{i,t}` = count × projection-share of EBITDA addbacks per facility-year. Projected addbacks (synergies, cost savings) *cannot* be recomputed from financials — that is Ivashina-Vallée "weakness" measured directly, not inferred.

---

## 2. Literature positioning

| Paper | What they did | What we add |
|---|---|---|
| Nini, Smith, Sufi (JF 2012) | Violation → creditor control | Realized slack distribution feeding the violation event |
| Chava & Roberts (JF 2008) | Violation → investment cuts | Same test with measured slack (attenuation comparison is a result) |
| Demerjian & Owens (RAST 2016) | *Estimated* probability of violation | Direct measurement replaces the model |
| Ivashina & Vallée (2020) | Weak covenant *terms* | Addback computability = weakness, measured |
| Li, Neamtiu, Tu (TAR 2024) | Withholding of covenant details | **Complement:** our slack predicts their withholding (H1 below) |

---

## 3. Data stack

| Source | Use | Access |
|---|---|---|
| SEC EDGAR (submissions API + full-text search) | Contract corpus (EX-10.x credit agreements, 8-K Item 1.01) | Public, 10 req/s |
| LSEG Loan Connector (WRDS) | Facility → GVKEY/PERMNO link | Seat — verify vintage |
| LSEG DealScan (WRDS) | Coded covenant fields = validation cross-check (NOT ground truth) | Seat — verify module |
| Compustat / CRSP / IBES (WRDS) | Controls, returns, outcomes | Seat |
| Calcbench (WRDS) | XBRL structured footnotes = recomputation leaves | Seat |
| Audit Analytics (WRDS) | Restatement outcomes | Seat |

---

## 4. Sample

- Universe: Loan Connector facilities, borrowers with GVKEY, signing years **2012–2025** (exhibit text quality; earlier years = scanned PDFs, excluded with note).
- Covenant types in scope (top 4 by DealScan frequency, expected): max Debt/EBITDA (leverage), min Interest Coverage, min Fixed Charge Coverage, max Capex. Net worth/min EBITDA optional.
- Expected yield (order-of-magnitude, to be replaced by pilot counts): ~10-20k facilities → ~4-8k matched exhibits → ~8-15k covenant observations. **Report actuals, never these estimates.**

---

## 5. Pipeline (6 stages — each individually testable)

```
EDGAR corpus → [S1 Locate] → [S2 Classify] → [S3 Extract] → [S4 Resolve] → [S5 Recompute] → [S6 Freeze/emit]
```

- **S1 Locate:** full-text search + filing-index scan; candidates = EX-10.x in 8-K (Item 1.01), 10-K, 10-Q. Signature regex: "Credit Agreement", "Amended and Restated", facility amount, agent bank block.
- **S2 Classify:** is-credit-agreement classifier. Target precision ≥0.95 on 200 hand-checked. Version clustering: same facility across amendments (borrower + date proximity + title similarity).
- **S3 Extract:** per covenant → Pydantic schema: `{type, metric_name, threshold_init, stepdowns[{date, value}], test_frequency, definition_spans[], addbacks[{item, cap, projected:bool}], equity_cure:bool, span_offsets[]}`. Every field carries pointer offsets (Lab 3 rule).
- **S4 Resolve:** definition chain → DAG ("Consolidated EBITDA means Consolidated Net Income plus (a)…(b)…"). Detect cycles / missing definitions → **flag, never guess** (WARN_NO_DATA honesty rule from Vidhi).
- **S5 Recompute:** map DAG leaves to XBRL tags (Calcbench) / Compustat items. Recompute metric per quarter; slack per covenant. Non-computable leaves → mark addback projected (counts toward `addback_index`).
- **S6 Freeze:** SHA-256(schema JSON + verdict + rule version) before any prose rendering (Safety-B pattern).

---

## 6. Validation battery (the moat)

| Layer | Test | Pass bar |
|---|---|---|
| L1 | Deterministic re-run of 10%, byte-compare | 100% match |
| L2 | Hand audit, 150 covenant extractions | field precision/recall ≥0.90 |
| L3 | DealScan cross-check on shared fields (type, initial threshold) | agreement ≥0.80; every disagreement in a reviewed queue |
| L4 | Adversarial: inject altered thresholds/addbacks | critic block rate ≥0.95, 0 privileged writes |
| L5 | Sanity: violation-rate time series vs Nini-Smith-Sufi estimates | same sign/shape; divergences explained |

---

## 7. Empirics (3 tables, 1 hypothesis)

- **T1 (first picture):** distribution of realized slack by type/year; covenant-lite vs maintenance.
- **T2 (drift):** addback count/share over facility life; event = amendment after performance decline.
- **T3 (real effects):** investment around slack→0; measured-slack vs Demerjian-Owens estimated-slack design comparison.
- **H1 (the Li-Neamtiu-Tu bridge):** disclosure withholding increases as *measured* slack decreases. Testable only with our measure — this is the paper's claim to necessity.

---

## 8. Timeline (12 weeks)

| Wk | Deliverable |
|---|---|
| 0 | Day-1 access checklist (§0) all green or scoped down |
| 1-2 | S1+S2; contract corpus v1; precision report on 200 |
| 3-5 | S3+S4 on 500 covenants; DAG success rate report |
| 5-7 | S5; slack panel v1; L1+L2 validation |
| 8-9 | L3+L4+L5; validation memo (shareable with prof) |
| 9-12 | T1-T3, H1; 15-page draft; India scoping note |

**Dinner demo (end of Wk 2):** one printed table — 5 facilities × extracted covenant chain vs contract span, plus slack time series for 1 firm.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| Exhibit-ID precision too low | Restrict to 8-K Item 1.01 attachments first (highest signal) |
| Definition DAG failures >15% | Scope to leverage + interest coverage only; report flag rate honestly |
| Projected addbacks non-computable | Feature, not bug — feeds `addback_index` |
| DealScan coverage gaps (private placements) | Sample = public filers; acknowledge selection |
| Vintage of Loan Connector <2020 | Sensitivity: 2012-2019 window; note in draft |
| Someone scoops (de Kok, Batta pipelines active) | Speed + India angle + the H1 bridge they don't have |

---

## 10. Kill criteria (fixed today)

- S2 precision <0.90 → stop, rethink identification.
- DAG resolution success <70% → stop, re-scope.
- L2 field accuracy <0.90 → stop.
- L3 agreement <0.70 with no explainable pattern → stop; report negative result.

---

## 11. Costs

LLM extraction ~5-10k covenant sections × ~4k tokens, cached: **est. $40-120** total. Compute trivial. Time is the only real cost.

## 12. India note (honest)

Indian loan agreements are NOT public. India mirror for this project is weak: possible only via (a) adjusted-EBITDA presentations vs Ind AS XBRL, (b) MCA charge filings (CHG-1) metadata. **Do not pitch India here** — pitch it on the BRSR/UCR program instead. This paper wins on the US data alone.
