# vidhi — Clean-Room Rebuild: Design Contract
> Naming note: `vidhi2` was the rebuild codename; the shipped package is
> `vidhi/`. There is one system, not two — old `vidhi/` references below mean
> the pre-rebuild prototype.

Goal: end-to-end rival to MoSPI StatsDoc that wins on trust and matches it
on headliners. New package; the old `vidhi/` keeps running untouched until
vidhi2 meets or beats every measured number below.

## Non-negotiable guarantees (each has a test in tests/test_vidhi.py)

1. **Rules judge, models translate.** No LLM output can change a verdict.
   Verdicts come only from versioned deterministic rules.
2. **Freeze before retrieval.** SHA-256(claim + decision + reason + rules)
   is computed BEFORE any document text is read. Poisoned chunks cannot
   move a verdict (Safety-B test: identical hash with/without injection).
3. **No threshold is safe.** Danger/paraphrase cosine ranges overlap on
   every measured embedder, so cache reuse requires exact match on all
   critical fields (field-guard test: 0 collisions across 19 danger pairs at any threshold).
4. **No PASS without provenance.** A numeric answer requires a `verified`
   store row whose value traces to cited source text (audit gate:
   `vidhi2_audit` fails the build otherwise). Anything else is WARN/REFUSE.
5. **Attribution is conservative.** Post-retrieval consistency only
   contradicts on same round + same filters + same measure basis + same
   unit. Ambiguity is never contradiction (regression tests from the
   top_k=5 incident: %-gaps, round-segment ownership, imputation basis).
6. **Honest coverage.** Uncovered slices get WARN + a live-computed note
   naming the requested slice and closest verified context, never endorsed.

## Planes (dependencies point down only)

```
service / demo / mcp / agent        <- thin; no logic
pipeline (ask)                      <- orchestration + traces + cost
render + consistency + retrieve     <- post-freeze only (untrusted text)
rules (5-stage firewall + freeze)   <- the judge
claims (schema + heuristic extract) <- the translator
store (built artifact + manifest)   <- generated, never hand-edited
sources (factsheet / plfs parsers)  <- machine extraction w/ provenance
```

Cross-plane rule: nothing above `rules` may alter a verdict; nothing may
read store rows except through `store.lookup` (verified-only).

## End-to-end (one command)

`make vidhi2` = ingest sources -> build store -> audit store ->
run eval (golden + danger + safety-B + thresholds) -> serve.
Any step failing stops the chain with a non-zero exit.

## What "compete with StatsDoc" means, measurably

| Dimension | StatsDoc (observed) | vidhi2 bar |
|---|---|---|
| Headline figures (MPCE/LFPR/UR/WPR) | correct, slow, costly | same figures, PASS with row_id + hash |
| Definitions | hallucinates MPCE expansion | canonical, metadata-pinned |
| Cross-break comparisons | silent wrong math | WARN/REFUSE with cited rule |
| Poisoned context | vulnerable | frozen verdict, hash unchanged under injection |
| Uncovered slices | guesses | honest WARN + coverage note |
| Cost / latency | $0.02-0.05, 3.5-8 s | $0.00, p95 ms-scale, offline |
| Coverage growth | manual | one parser per table family + audit |

## Build order (each step green before the next)

- [x] 1. claims + schema tests (4 tests)
- [x] 2. store + sources/PLFS + sources/factsheet + audit (173/173 reproduced)
- [x] 3. rules + freeze + stage-order tests
- [x] 4. guard + retrieve + render + consistency (+3 regression tests)
- [x] 5. pipeline + service + eval + demo
- [x] 6. Cross-check: identical verdicts to vidhi/ on all 100 golden,
  100/100 reason parity, stable at top_k 3/5/10
- [x] 7. ConfAI materials re-pointed (README / demo / evaluation report unified on 100 golden + 173 verified rows)

## Flexibility record (no hardcoded values; APIs where they help)
- eSankhyiki live API answers what the frozen store cannot
  (`_live_source` in pipeline): urban Bihar female LFPR 2023-24 = 16.7%,
  urban female LFPR 2025 = 27.7% (the latter cross-checked against PDF
  Table 1). Governance verdicts never move (still WARN); a separate
  `evidence_tier` (VERIFIED | SOURCED | NONE) labels provenance, and
  SOURCED answers are explicitly "sourced, not certified".
- Positioning: governance + sourcing layer that StatsDoc could plug in,
  not a rival assistant. REFUSE is reserved for speculation, politics,
  and injections -- never for answerable numbers.
- NVIDIA NIM translator (`translate()` + VIDHI2_USE_LLM=1), measured
  agreeing with the heuristic; heuristic stays the offline default.
- PDF parsers carry the brittleness honestly: one parser per table
  family, each raising (not guessing) on layout drift; the audit gate
  catches everything else.

## Big-tech review (Meta / Google / Microsoft lens)

What they would steal: the pre-retrieval freeze (their guardrails are
mostly post-hoc text filters -- jailbreakable; ours structurally prevents
verdict tampering), evidence-tier labeling (matches their grounding-UX
direction), and dual-source agreement (their cross-validation practice).

What they flagged and we fixed:
1. Retrieval was unranked keyword overlap -- the weakest component.
   Now bi-encoder rerank (bge-small, 0.7 cosine + 0.3 keyword) with
   index-time excerpt vectors and startup warmup (no first-query cliff).
   Proven: rerank surfaced two real attribution bugs the keyword order
   had hidden (pair-claim exclusion, small-counter skip).
2. Eval at 100 golden is a demo, not a practice. They run thousands with
   judges + humans. Our answer: keep 46 as the CI gate, grow adversarial
   coverage next (danger 19 -> 50+ with paraphrase variants).
3. Safety as regex (aip.guards) is a demo control. Their bar: calibrated
   classifiers with measured precision/recall on red-team sets. Our
   injection REFUSE path stays, but its evaluation must scale likewise.
4. Freshness: scheduled rebuild + staleness alert on store manifest age.
   Not yet built -- ranked next after adversarial scale-up.

## Security review notes (for a MoSPI-developer bar)

- TLS: the third-party esankhyiki client disables certificate verification
  (InsecureRequestWarning observed). Our adapter inherits that weakness on
  the release-time path. Required before any MoSPI-internal use: verify
  against api.mospi.gov.in with a pinned CA, or route through the
  Ministry\'s own gateway. The query-time path is unaffected (offline).
- Secrets: NVIDIA_API_KEY lives in .env (gitignored) and is never logged;
  microdata keys follow the same rule (vidhi/microdata.py). Production
  needs a secret manager, not .env.
- No load test yet (Lab 7 stretch item): 20-concurrent behavior unknown;
  expected first bottleneck is the SQLite/file cache lock, unmeasured.
- Deployment: Dockerfile provided (CPU-only, store baked at build time,
  embedding index warmed at startup). No helm/k8s manifests, no
  monitoring/alerting yet.
