# StatsDoc observation protocol (reproducibility repair)

Status: HONEST DISCLOSURE. The "Sessions #2402 & #2399" figures cited in
decks and notes are contemporaneous observations from live testing of
`statsdoc.ai.mospi.gov.in`, not committed transcripts: no screenshots or
session logs were archived at the time. Every claim about StatsDoc below
is therefore ANECDOTAL until re-run under this protocol. Do not present
it as a measured baseline.

## Reproducible prompts (re-run against the live pilot)

1. MPCE definition: "What is MPCE in HCES?" Record the exact expansion
   given (observed: "Mean Per Capita Expenditure" instead of the statutory
   "Monthly Per Capita Consumption Expenditure"). Archive: full response
   text + timestamp + session/chat id in `sessions/` (create it).
2. Comparability: "How much has real rural MPCE grown between 2011-12
   and 2023-24?" Record whether ANY caveat about the paper-to-3-visit-CAPI
   break (HCES Statement 2 / MMRP note) accompanies the growth figure.
3. Arithmetic: "Rural MPCE was Rs 3,773 in 2022-23 and Rs 4,122 in
   2023-24; urban Rs 6,459 and Rs 6,996. What is the two-year compound
   picture?" Record whether the synthesis is attempted and whether it is
   flagged as unofficial.
4. Latency/cost: record time-to-first-token wall-clock per prompt (3 runs)
   and the pilot's disclosed model/pricing if any.

## Rules for citing StatsDoc in this repo

- Allowed: "observed failure modes (prompts in PROTOCOL.md, re-runnable)".
- Not allowed: "measured audit", "benchmarked", sample sizes, or
  latency/cost numbers presented as our measurements. The $0.02-0.05 and
  3.5-8 s figures are order-of-magnitude estimates from the pilot's
  behavior class (hosted LLM RAG), not metered observations: label them so.
