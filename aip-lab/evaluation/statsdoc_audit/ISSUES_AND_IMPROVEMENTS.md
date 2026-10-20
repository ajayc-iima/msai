# StatsDoc audit — issues found and Vidhi improvements shipped

This is the student-audit write-up: a thorough pass over the MoSPI StatsDoc AI
Assistant (βeta) pilot (`https://statsdoc.ai.mospi.gov.in/`) and the public
MoSPI data layer underneath it, with the gap each finding motivated in Vidhi.

Sources: `ACCESS_2026-10-20.md`, `COMPARISON.md`, `PROTOCOL.md`,
`sessions/2026-10-20/` (login wall, redirect, signed-in surface, transcripts
`definition.txt` … `injection.txt`, `esankhyiki_probe.json`), and the
reverse-engineered SvelteKit bundle (`/tmp/opencode/sd_bundle/`, 102 files).

## A. What StatsDoc is (measured)

- **Account-gated** (`/` and every `/c/<id>` → `/login`; `POST /api/login/`
  throttles). Pilot is beta.
- **Document-scoped chat**: "Select document and start conversation with
  that!" — one chat per selected document, WebSocket (`wss://…/ws/chat/?token=`).
- **35 knowledge bases** (National Accounts, CPI, GDP, PLFS, HCES, ASI, SDG,
  Energy, 80th Round, …) + **user-uploaded knowledge bases** (CRUD + file
  upload, ≤5 files) mixed into the same corpus with no provenance separation.
- **3 languages**: English, Hindi, Kannada (`/chat/languages/`).
- **Retrieval**: Qdrant (`qdrant_data.citations` / `qdrant_data.context`
  embedded in the assistant message as a Python-dict string, parsed
  client-side with `replace(/'/g,'"')` + `JSON.parse` — citations can
  silently vanish).
- **Citation shape**: `{document_name, document_link, content}` —
  document-chunk level, **no page, table, row or figure id**.
- **Disclaimer (verbatim)**: "powered by third-party Large Language Models …
  responses generated should not be taken as evidence or treated as official
  communication … MoSPI makes no warranties regarding accuracy, completeness,
  or reliability … Users are strongly cautioned to verify …"
- **Fallback string**: "I could not find this information in the uploaded
  documents. Please try rephrasing your question."
- **Feedback taxonomy** (8 reasons): incorrect/incomplete, not-what-asked,
  wrong-document, language-issue, slow/buggy, style/tone, safety/legal, other.
- **Admin surface**: analytics dashboard (`/chat/analytics/dashboard/`),
  per-chat view (`/chat/view/<id>?user=`), manager report export
  (`StatsDoc_Manager_Report_*.docx`), bulk user upload.
- **Security nit**: JWT in the WebSocket URL query string (access-log
  leakage).
- **Data layer underneath**: eSankhyiki (`api.mospi.gov.in`) — state cuts,
  education/religion/social-group cuts, 0.3–0.4 s/query; "2027" →
  "No Data Found".

## B. Issues found (the audit)

1. **Numeric inconsistency within a single answer.** Madhya Pradesh MPCE:
   "Rural 3,158 / Urban 5,011 (or 5,589)"; "All: 3,441 / 3,522";
   "All: 5,538 (or 4,987)". Chunk-stitching produced conflicting figures in
   one answer, with no way for the reader to tell which is right.
2. **Short codes not resolved.** "What is the MPCE in mp?" → the assistant
   returned the generic definition of MPCE, ignoring "mp".
3. **Generic abstention.** Out-of-corpus and out-of-scope questions both get
   "I can only answer questions based on the uploaded document." — no
   coverage map, no nearest slice, no distinction between "not in corpus"
   and "out of scope".
4. **No comparability caveat.** The 40% rural real growth (2011-12 →
   2022-23) is quoted without the paper→CAPI method break that makes the
   level comparison unsafe; the 2011-12 → 2023-24 figure is simply "not
   provided in the text".
5. **Citations are document-chunk level** with no page/table/row/figure id,
   parsed client-side from a fragile Python-dict string.
6. **Disclaims everything.** "should not be taken as evidence or treated as
   official communication" — the system disclaims the one property a citizen
   needs (authoritativeness).
7. **Mixed provenance.** User uploads share a corpus with official reports
   with no separation.
8. **"Mean Per Capita Expenditure" anecdote was wrong.** The live pilot now
   says "Monthly Per Capita Consumption Expenditure" — corrected in
   `COMPARISON.md`; the comparison no longer cites the old string.
9. **Forecast questions get the generic abstention**, not an explicit
   "no data for 2027" (the layer returns "No Data Found").

## C. Vidhi improvements shipped in response

- `vidhi/states.py`: added `suggest_state()` / `suggest_states()` — a
  "Did you mean …?" hint for typos/unknown places, gated so it never fires
  for known places, short tokens or anything too far from a curated name
  (Atlantis → no suggestion).
- `vidhi/claims.py`: the definitional "what is …" branch no longer fires
  when an unknown geography is present, so "MPCE in Atlantis" now abstains
  instead of returning methodology.
- `vidhi/rules.py`: the unknown-geography WARN now appends the suggestion
  ("Did you mean 'Bihar'?").
- `vidhi/demo.html`: structured feedback widget adopting StatsDoc's 8-reason
  taxonomy, logged with verdict/reason/trace context.
- `evaluation/statsdoc_audit/COMPARISON.md`: filled in with measured
  StatsDoc answers (transcripts `sessions/2026-10-20/*.txt`, chats 2472–2480)
  replacing the "pending transcript" placeholders.
- `scripts/statsdoc_probe.py`, `scripts/vidhi_probe.py`: reproducible probes
  (credentials from env vars only).

## D. What Vidhi still does NOT do (honest gaps)

- Hindi/Kannada answers (we refuse injection in Hindi/Hinglish but answer in
  English only). StatsDoc wins on languages.
- Live breadth (state-level labour, education/religion cuts, district
  tables). StatsDoc wins on coverage; Vidhi keeps these as SOURCED (not
  certified) tier.
- Multi-document Q&A across the whole MoSPI catalogue. Vidhi is four PDFs.

## E. Tests

`python -m pytest tests/ -q` → 117 passed. `python vidhi/eval.py` →
verdict/reason/numeric/citation 1.000, abstention recall 1.000,
hallucination 0.000.
