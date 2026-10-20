# Project TWO TRUTHS — Cross-Framework Reconciliation of BRSR and GRI Disclosures
**Status:** Pre-pilot plan · 2026-10-05 · Author: Ajay Choudhary (MSAI, Plaksha)
**Target collaboration:** ISB Accounting (K. Balakrishnan — information production; G. Sandhu — disclosure/credit)
**Program:** Paper 3 of the machine-verifiable disclosure engine (after US covenant slack, India NCD slack)

---

## 0. Evidence status

**VERIFIED this session (OpenAlex, 2026-10-05):**
- No within-firm, cross-framework *numeric* reconciliation study exists (searches: cross-framework consistency, GRI×TCFD divergence, GRI×BRSR). Gap open.
- Competition is weak: Bhowmick & Mahindrakar (Frontiers in Sustainability, 2026, ×2) — GRI-BRSR *coverage checklists*, single sector, qualitative; Mandviwala (2025) — descriptive; Shankar & Xu (SSRN 2025) — NLP text classification, no verification.
- Adjacent, must cite: Avidan, Walls, Dowell (J. Bus. Ethics 2026) — *temporal* (cross-year) inconsistency. Ours is *within-year, cross-framework*. Different.
- Design template: Fiechter, Hitz, Lehmann (JAR 2022), EU CSR mandate real effects, 400 cites.
- Venue proof: Grewal, Richardson, Wang (TAR 2026), mandatory carbon reporting → greenwashing.
- Mechanism anchor: Berg, Koelbel, Rigobón (RFS 2022), *Aggregate Confusion* — 56% of ESG rating divergence is measurement. We test the upstream disclosure cause.
- Outcome anchor: Aobdia, Köchling, Limbach (2025 WP) — emissions restatements in CDP.

**ASSUMED — verify Day 1:**
- [ ] BRSR mandatory top-1000 from FY22-23; voluntary FY21-22 (SEBI circular ~May 2021).
- [ ] BRSR Core assurance phase-in: top 150 FY23-24 → top 250 FY24-25 → top 500 FY25-26 → top 1000 FY26-27 (verify exact cohorts; July 2023 circular; sebi.gov.in blocks bots — check manually).
- [ ] BRSR filed on **standalone** basis; GRI reports typically **group-level** — the boundary asymmetry this paper exploits. (Verify from BRSR instructions.)
- [ ] ≥150 of top-250 dual-report (BRSR + GRI) — estimate, must count.
- [ ] Sustainalytics/MSCI/ISS ESG cover ≥60% of the sample on our WRDS seat.
- [ ] GRI report retrieval at volume (GRI Sustainability Disclosure Database terms, or company IR sites).
- [ ] Whether exchanges collect BRSR in XBRL (would ease extraction enormously).

---

## 1. One-line pitch

> Top Indian firms publish two quantitative sustainability disclosures for the same year — BRSR (mandatory, regulator-facing) and GRI (voluntary, investor-facing). Within-firm-year, divergence cannot be fundamentals: it is measurement choice. We build the first reconciliation panel and ask: which audience gets the flattered number, and what does the wedge predict?

**Construct:** `CFDS_{i,m,t}` (Cross-Framework Divergence Score), per firm i, metric m, year t — with verdicts CONSISTENT / EXPLAINED-BY-BOUNDARY / CONTRADICTORY / UNRESOLVABLE.

**Theoretical framing (the sharp edge):** audience-dependent measurement. Selective disclosure under scrutiny (Marquis, Toffel, Zhou, Org Sci 2016) + organized hypocrisy/façades (Cho, Laine, Roberts, Rodrigue, AOS 2015) + greenwashing drivers (Delmas & Burbano, CMR 2011). Ex-ante ambiguity is the design's strength:
- H_a: GRI flattered (investor scrutiny → impression management).
- H_b: BRSR flattered (regulatory scrutiny → compliance theater).

---

## 2. Metric map (pilot scope — 6 metrics)

| # | Metric | BRSR location | GRI standard | Unit chains |
|---|---|---|---|---|
| 1 | Energy consumption | P6 essential (GJ) | GRI 302-1 | GJ/TJ/MWh/kWh |
| 2 | Scope 1 GHG | P6 (tCO2e + intensity) | GRI 305-1 | tCO2e |
| 3 | Scope 2 GHG | P6 | GRI 305-2 | location vs market-based flag |
| 4 | Water withdrawal/consumption | P6 (KL) | GRI 303-3 / 303-5 | KL/m³ |
| 5 | Waste generated | P6 (MT) | GRI 306-3 | MT/t |
| 6 | Women in workforce %; turnover; LTIFR | P3 | GRI 405-1; 401-1; 403-9 | rates |

(Exact BRSR indicator numbers: verify from format doc Day 1 — cite by content, not number, until then.)

---

## 3. Pipeline (engine reuse — 6 stages)

```
dual-report corpus → [S1 Locate] → [S2 Extract] → [S3 Normalize] → [S4 Reconcile] → [S5 Freeze] → [S6 Emit CFDS]
```

- **S1 Locate:** BRSR from BSE/NSE annual report filings (check XBRL availability); GRI from GRI database / IR sites. FY alignment rule: map to Indian Apr–Mar FY; record GRI year convention.
- **S2 Extract:** KPI tables → Pydantic schema `{metric, value, unit, boundary_declared, assurance_flag, year_convention, span_offsets[]}`. Use GRI Content Index to locate indicators (standardized, easier than body prose).
- **S3 Normalize:** unit conversion; **boundary decision tree** (the intellectual core):
  1. Read boundary declarations in both docs (entity list, control approach).
  2. If boundaries align → direct compare.
  3. If differ → attempt adjustment from segment/subsidiary splits disclosed in either doc.
  4. Unresolvable → honest `UNRESOLVABLE` (Vidhi WARN_NO_DATA rule: never guess).
- **S4 Reconcile:** tolerance ±2%; three-way verdict per metric.
- **S5 Freeze:** SHA-256(schema + verdict + rule version) before any prose (Safety-B).
- **S6 Emit:** CFDS panel + citation trail.

---

## 4. Validation battery

| Layer | Test | Pass bar |
|---|---|---|
| L1 | Deterministic re-run 10% | byte-identical |
| L2 | Hand audit 150 metric extractions (2 raters) | precision/recall ≥0.90 |
| L3 | CDP responses as third source (subset) | triangulation agreement reported |
| L4 | Adversarial: inject altered KPIs | critic block ≥0.95 |
| L5 | Sanity: sample aggregates vs published sector stats | same order of magnitude, divergences explained |

---

## 5. Empirics

- **T1:** CFDS distribution by metric — first picture of cross-framework divergence.
- **T2 (the headline):** directionality — sign test on CONTRADICTORY cases; which framework is flattered (H_a vs H_b).
- **T3:** drivers — assurance status, Big4 assurer, FII ownership, promoter ownership, ESG-linked loans.
- **T4:** consequences — ESG rating divergence (Aggregate Confusion measurement channel), RepRisk incidents, BRSR restatements.
- **H1 (DiD):** BRSR Core assurance phase-in (staggered cohorts) → CFDS reduction. Callaway–Sant'Anna; never-treated = not-yet-mandated cohorts.

---

## 6. Sample

- Frame: top-250 BSE/NSE by market cap (first assurance cohorts) × FY22-23 → FY24-25.
- Est. dual-reporter overlap: 150-250 firms (verify Day 1) → ~300-600 firm-years × 6 metrics ≈ 2-4k reconciliations. Report actuals.

## 7. Timeline (12 weeks)

| Wk | Deliverable |
|---|---|
| 0 | Day-1 checklist (§0) green or scoped |
| 1-2 | S1 corpus; overlap count; extraction POC on 10 firms |
| 3-4 | S2+S3 on pilot metrics; boundary tree v1 |
| 5-6 | S4 verdicts on 50 firms; L1+L2 |
| 7-8 | Full sample; L3+L4+L5; validation memo |
| 9-12 | T1-T4, H1; 15-page draft; ESRS×GRI extension note |

**Dinner demo (Wk 2):** one table — 5 firms × 6 metrics × verdicts, spans cited.

## 8. Risks

| Risk | Mitigation |
|---|---|
| GRI PDFs are design-heavy (hard extraction) | Content Index first; layout-aware extraction; fall back to tabloid pages |
| Boundary unresolvable >40% | Narrow to energy + Scope 1/2 (cleanest); report unresolvable share honestly |
| Assured cohort small in FY23-24 (top 150) | Pool FY23-25; note power |
| India rating coverage thin | Mechanism test moves to CDP/restatement outcomes |
| Bhowmick-Mahindrakar extend | Speed; they lack the reconciliation engine + outcomes |

## 9. Kill criteria

- Dual-reporter overlap <100 firm-years → stop.
- UNRESOLVABLE >40% → stop (boundary problem is fatal, not fixable).
- CONTRADICTORY rate <2% → no variation, measure dead → stop.
- L2 accuracy <0.90 → stop.

## 10. Costs

~1,500 documents; cached LLM extraction ≈ **$100-250**. Time dominates.

## 11. Generalization (the prize beyond India)

CSRD/ESRS × GRI double-reporting in Europe began with FY2024 reports (published 2025), with mandated *limited* assurance. Same engine, second continent, second assurance DiD. India is the proving ground; Europe is the sequel.

## 12. Fit

- **Karthik:** "who has what information, how it is produced, what happens when distorted" — CFDS is information production choice measured directly. Venue proof exists in his own journal (Grewal TAR 2026).
- **Gurvinder:** ESG-credit channel (NCD spreads, ESG-linked loans) as outcomes if he joins.
- **Award tracks:** sustainability/disclosure best-paper; policy impact (SEBI, GRI, ISSB are natural consumers).
