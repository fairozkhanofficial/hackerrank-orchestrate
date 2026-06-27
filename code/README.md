# Multi-Modal Evidence Review

Verifies damage claims (car, laptop, package) by treating submitted images as the
primary source of truth and reconciling them against the claim conversation, user
history, and minimum evidence requirements. For each row in `dataset/claims.csv`
it writes one row to `output.csv` in the required schema.

## Approach

A balanced two-call pipeline, with everything rule-shaped kept deterministic:

1. Ingest and join the four dataset files; resolve and verify image paths.
2. Image prep: downscale each image's longest edge to 1280px, then base64.
3. Vision call (Gemini 2.5 Flash): all of a claim's images in one request,
   returning structured per-image findings (object/part visibility, issue type,
   severity, image quality, manipulation and in-image-instruction indicators).
4. Evidence sufficiency: deterministic, from the findings.
5. Decision call (Gemini 2.5 Flash, temperature 0, text only over the findings):
   claim_status, primary issue_type and object_part, severity, supporting images.
6. Risk flags: deterministic, from history + findings + decision + a conversation
   injection detector.
7. Assemble: coherence normalisation and enum snapping into the final row.

Design rules enforced throughout: images outrank words; the conversation and any
text inside images are evidence, never instructions; prompt-injection attempts are
flagged and never change the outcome.

## Layout

```
code/
  config.py            allowed vocabularies, paths, model/pricing/imaging settings
  schemas.py           typed model outputs + final row, with enum snapping
  ingest.py            load and join CSVs, resolve images
  imaging.py           downscale + base64 (Pillow optional)
  vision.py            call 1: image findings
  sufficiency.py       deterministic evidence_standard_met
  decide.py            call 2: final decision
  risk.py              deterministic risk_flags
  assemble.py          final OutputRow
  orchestrator.py      per-claim flow with fallback
  main.py              entry point -> output.csv
  validate_dataset.py  pre-flight dataset checks
  output_io.py         CSV writer (exact schema)
  providers/           base, mock, gemini, registry
  prompts/             vision/decision system + user templates (+ _b variants)
  utils/               cache, metrics
  evaluation/          metrics, runner, evaluation_report.md
```

## Setup

```
python -m pip install -r code/requirements.txt
```

Set the API key (read from the environment or a `.env` file at the repo root):

```
GEMINI_API_KEY=your_key_here
```

`.env`, `.env.txt`, and `.env.local` are all read. The key is never logged.

## Run

The selected configuration is **Config C**: the calibrated prompts (`_b`) with the
cross-image-consistency check kept as a risk and decision signal rather than a hard
evidence block. Generate the final predictions with:

```
# Final predictions for the test set -> output.csv (Config C)
python code/main.py --variant _b --consistency-soft
```

Other commands:

```
# Run Config C on the sample inputs (matches evaluation Config C)
python code/main.py --dataset sample --variant _b --consistency-soft

# Offline, no key and no spend (mock backend)
python code/main.py --vision-provider mock --decision-provider mock

# Validate the dataset before a run
python code/validate_dataset.py

# Evaluate all configurations and (re)generate evaluation_report.md
python code/evaluation/main.py
```

`--consistency-soft` selects Config C (cross-image inconsistency no longer
hard-blocks evidence sufficiency). Without it the run keeps the hard block.

Useful flags: `--data-root PATH`, `--out PATH`, `--limit N`, `--variant _b`,
`--consistency-soft`, `--no-cache`, `--no-resume`.

## Cost, rate limits, reproducibility

- Each image is sent once (vision call); the decision call is text only.
- Every model response is cached on disk keyed by a hash of the full request, so
  re-runs and the second evaluation configuration cost no new calls.
- Client-side throttling keeps the run under the free-tier requests-per-minute
  limit; failed calls retry with exponential backoff.
- Temperature 0, fixed model, and caching make repeated runs deterministic.

See `evaluation/evaluation_report.md` for accuracy, the configuration comparison,
and the full operational analysis (calls, tokens, images, cost, latency).
