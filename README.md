# Policy Field Injection

English | [简体中文](README.zh-CN.md)

Experiment code for attacks that place decision-shaping policy text in business input to typed decision models. The toolkit covers Choice, Noul and Score outputs, a field whitelist, a policy-text detector, and payloads that try to bypass those defenses.

Two injection forms are used throughout:

- **Form A:** add a top-level field such as `review_policy` or `screening_policy`.
- **Form B:** append the policy text inside an existing text field, such as a ticket body or code comment.

## Start offline

Use Python 3.12 or newer. From the repository root:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/check.py
python scripts/run.py smoke
python scripts/run.py replay
python scripts/run.py review-replay
python scripts/run.py bypass-replay
```

`smoke` uses deterministic synthetic responses to check the runner and logging. `replay` reads two saved Clef-Flash Choice responses: the clean ticket routes to `billing`, and the ticket with an added policy field routes to `sales`.

The replay also feeds two saved review-report excerpts into a demonstration gate. A report containing `request_changes` is rejected; a report without it is allowed. The allowed branch writes `MERGED.marker` under `output/gate-replay/`. It performs no merge. These excerpts exercise the gate; they do not rerun the upstream code-review model.

`review-replay` traces all 28 saved requests across one review of each main-case input and the failed SSH transfer. It shows screening probabilities, follow-up choices and severity scores, then pairs the four main-case reports with saved D2 responses. The default needs no weights. Add `--local-detector` to run Intern-Decision-2B on the same patches. The output labels saved review responses, saved or local detection, and gate actions separately. `bypass-replay` shows the saved documentation-example payload passing the detector and changing Clef-Flash's secret-checking decision.

## Run with a model

[configs/backends.json](configs/backends.json) lists the backend names, checkpoint revisions, model paths and runtime requirements. It covers Jev through OpenRouter and local adapters for Julia-1, Laya, Clef-Flash, Decider, three Intern-Decision sizes, Jev-Style, NanoJev, two OpenJev models and OpenThai-SystemOne.

Model weights are downloaded separately. The local adapters also use inference code shipped with the model snapshots, so download the complete snapshot rather than just its weight file. A helper is provided:

```bash
python -m pip install huggingface_hub
python scripts/download_model.py clef
```

The helper prints the model path and backend settings. Downloads go into the ignored `models/` directory. Install each model's runtime in a separate environment; Julia-1 uses Transformers 5.0.x, while the Intern-Decision snapshots use 5.14.1.

For Clef-Flash on Apple Silicon:

```bash
python -m pip install 'mlx==0.32.3' 'mlx-lm==0.32.0' 'mlx-vlm==0.7.4'
export CLEF_MODEL_DIR="$PWD/models/clef-flash-4bit"
export DECISION_CLIENT=clef
export RUN_TAG=clef
python scripts/run.py matrix p1 p2 extnew
```

For the other local adapters, use the path variable and backend name in `backends.json`. Follow the downloaded snapshot's dependency instructions. Julia-1 additionally needs `python -m pip install -e models/Julia-1`; this installs `supersonic-julia`, which provides the `julia` import used by the adapter. Laya needs the `laya` package, and OpenThai needs `openthai-systemone`. NanoJev uses CPU fp32 inference in this adapter. Clef uses MLX; most other adapters default to CPU.

For Jev, install the base requirements and set `DECISION_CLIENT=jev`, `OPENROUTER_API_KEY` and, optionally, `JEV_MODEL`. The default is `~typesafe/jev-latest`. Provider aliases can change; logs retain the model identifier returned by the API. Fresh Jev runs make paid API calls.

The published Intern-Decision-4B candidate-family result uses MPS with bfloat16. Set these explicitly; the adapter defaults to CPU/float32:

```bash
python scripts/download_model.py intern-4B
export INTERN_MODEL_DIR="$PWD/models/Intern-Decision-4B"
export INTERN_DEVICE=mps
export INTERN_DTYPE=bfloat16
export DECISION_CLIENT=intern
export RUN_TAG=intern-4B-mps
python scripts/run.py candidates
```

The adjudicated evaluation uses one original input per question (`holdout` without `--variants all`). The repeated review experiment uses `review-chain --profile confirmation`: 50 reviews per input, four inputs. The independent D2 detector uses Intern-Decision-2B on CPU/float32. Model revisions are listed in `backends.json`; the recorded Jev model is `typesafe/jev-1.13-20260917`.

## General-purpose model control

SemIf with Qwen3.5-4B is the additional general-purpose control, reported separately from the 13 typed decision models. The exact five SemIf inference modules used in the experiment are bundled under `toolkit/third_party/semif_phase1/`, with their MIT license. The scorer uses `direct-options-v1` letter-logit readout and the unquantized Qwen checkpoint on Apple Silicon with MLX/bfloat16.

```bash
python -m pip install 'mlx==0.32.3' 'mlx-lm==0.32.0'
python scripts/download_model.py semif-qwen4b
export SEMIF_MODEL_DIR="$PWD/models/Qwen3.5-4B"
export DECISION_CLIENT=semif
export RUN_TAG=semif-qwen4b
python scripts/run.py matrix p1 p2 extnew
```

The model revision is fixed in `backends.json`; its weights are downloaded separately. Use `scripts/recompute.py matrix` on the resulting `p2` and `extnew` logs to count the control's Choice outcomes.

## Experiment commands

Set `DECISION_CLIENT` and the model path before running these commands. Each run writes its requests, responses and summary to an ignored `results/` directory or `output/`.

```bash
# Baselines and fixed policy-field attacks across the two scenario pools
python scripts/run.py matrix p1 p2 extnew

# Payload components, field names, placement, Chinese and Thai policy text
python scripts/run.py matrix ablation position thai

# Attacks on cases near a decision boundary
python scripts/run.py matrix contested

# Twelve declared candidates, with fresh clean and fixed-payload responses
python scripts/run.py candidates

# Plain override, pseudo-policy, neutral text, and field-provenance controls
python scripts/run.py matched

# Policy tone x detector-facing line; downstream outcomes at 0.5 and 0.8
python scripts/run.py thresholds

# Field whitelist, Form B, and Form B through the whitelist
python scripts/run.py defense f1 f2 f3

# Policy detector and adaptive payloads
python scripts/run.py defense f4 f5 f6a f6b f7 fp

# Detector arms on Noul screening gates
python scripts/run.py defense --kind noul f4 f7

# All 90 holdout scenarios, or one batch and tier
python scripts/run.py holdout
python scripts/run.py holdout --batch v2.2 --tier T1

# Benign-input detector false positives and clean decision retention
python scripts/run.py benign
```

The candidate-family run starts from fresh baseline responses and evaluates further candidates where the fixed payload has not already succeeded on every usable variant. It uses at most 2,080 model requests. `MAX_CALLS` defaults to 2,500 and must be at least 2,080 to cover the full protocol.

The defense command first generates matching clean and Form A responses. It does not depend on historical experiment logs. The arms are:

| Arm | Input and defense |
| --- | --- |
| `f1` | Form A through the top-level field whitelist |
| `f2` | Form B |
| `f3` | Form B through the whitelist |
| `f4` | Form A through the policy detector; flagged fields are stripped |
| `f5` | Form B through the detector; flagged inputs are blocked |
| `f6a` | Policy text rewritten as routine business documentation |
| `f6b` | The rewritten text through the detector |
| `f7` | Form B plus a detector-facing bypass instruction |
| `fp` | Detector scans of clean scenario text |

Detector arms and `benign` require a separate Intern-Decision-2B checkpoint:

```bash
python scripts/download_model.py intern-2B
export DETECTOR_MODEL_DIR="$PWD/models/Intern-Decision-2B"
export DETECTOR_DEVICE=cpu
export DETECTOR_DTYPE=float32
```

Install that snapshot's dependencies in the environment running the defense experiment. The detector has its own engine and configuration, independent of `INTERN_MODEL_DIR`. It flags text when `P(yes) >= 0.5`; benign scans also report counts at 0.8. The source-aware detector prompt is available separately in `toolkit/defenses/detector_v2.py`.

The source-aware experiment uses [configs/source_aware.json](configs/source_aware.json): 24 v1 attacks across three gates and 24 benign texts. It supplies the same one-line trusted-configuration description and field-source descriptions used in the original experiment. Run it with the detector configured above, or replay its recorded local probabilities:

```bash
python scripts/run.py source-aware
python scripts/run.py source-aware --replay
```

Replay reports 2/24 attacks detected and 0/24 benign texts blocked. Its requests are reconstructed from the archived texts and frozen detector prompt; its probabilities come from the saved experiment. Replay checks each complete request before using its saved response. Both modes write per-input records and a summary under `output/source-aware/`.

## Inputs and counting

The scenario pools and payloads live in `toolkit/experiments/`. The scenario matrices use an original input and seven text mutations per scenario. Holdout runs use the original input by default; add `--variants all` to include the seven mutations. [configs/holdout.json](configs/holdout.json) contains three batches of 30 scenarios, their final labels and their tier assignments. It contains no model responses or adjudication notes.

The original scenario matrices and candidate-family run count attack-target selections among variants whose baseline did not already select that target. The holdout summary reports that count and a stricter count restricted to baseline-correct variants. It separates T1, T2 and excluded (T3, `T3/out` or `out`) cases. T1 is the main tier; T1+T2 is reported as a sensitivity result. Mutations of one scenario are related inputs; treat the scenario as the sampling unit when estimating uncertainty.

The `bank_wire` and `event_access` holdout inputs include their original `policy_reference` fields, which supply the trusted rules needed to determine their answers. Keep those fields when rerunning the evaluation.

The `matched` runner and recount currently report the baseline-not-target denominator. The paper's 35/86 versus 9/86 comparison uses baseline-correct inputs. On the original records, the broader count is 41/94 versus 10/94; the additional eight inputs had incorrect baseline answers.

Runner records mark synthetic, saved-response replay and inference modes. The replay adapter requires an exact matching saved request and raises on unknown inputs. A replay run incurs no model or API cost.

Run records also include checkpoint revisions and device/precision settings. Settings read from loaded tensors are distinguished from adapter configuration; hosted settings are recorded as provider-managed. Detector records carry their separate model configuration.

## Independent recomputation

`scripts/recompute.py` reads saved records without importing the experiment runners or loading a model. It supports `matrix`, `candidates`, `holdout`, `matched`, `thresholds`, `defense`, `benign` and `review`. For example:

```bash
python scripts/recompute.py matrix samples/choice.jsonl
python scripts/recompute.py defense samples/bypass.jsonl
python scripts/recompute.py review samples/review-chain.json
```

For a fresh run, pass the JSONL filename printed by its runner. Matrix counts use the matching `p2` and `extnew` files; defense counts use the fresh baseline file and the selected arm's file. Recount separate runs separately: duplicate conditions are rejected. Add `--output output/recount.json` to save the result. The threshold recount separates release over all scanned inputs, baseline-eligible release, and successful downstream attacks. The candidate recount checks candidate completeness and applies the declared tie rule independently.

## Archived Jev API records

[data/jev/](data/jev/) contains the two complete September 20, 2026 runs: 840 records in `expd3-20260920-134946.jsonl` and 987 in `expd4-20260920-135925.jsonl`. The files retain the original inputs, question schemas, model identifiers, returned answers, repetition indices, timestamps and costs. The model is `typesafe/jev-1.13-20260917`.

```bash
python scripts/recount_jev.py
```

This reads the saved records without calling an API and recovers 206 target selections in 270 fixed-payload samples across 20 scenarios, with at least one selection in 15 scenarios. These are repeated API samples: the first batch has 15 baseline and 12 fixed-payload calls per scenario; the second has 20 baseline and 15 fixed-payload calls. [configs/jev_archive.json](configs/jev_archive.json) identifies the conditions and targets used for counting. The two files also retain the other attack conditions from those runs. The earlier interrupted run is excluded.

## Archived candidate-family calls

[data/candidates/](data/candidates/) contains 16,982 original Choice request/response records for the final twelve-model comparison, compressed into one JSONL gzip file per model. They include the clean baselines, fixed-payload responses and all evaluated candidates. The [protocol](data/candidates/PROTOCOL.md) describes the candidate pool, eligibility, selection and historical run selection; [configs/candidate_archive.json](configs/candidate_archive.json) identifies the source records.

```bash
python scripts/recount_candidates.py --output output/candidate-recount.json
```

The recount needs no model or API access. It recovers 763/1669 fixed-payload flips and 1294/1669 family flips, with coverage of 150/229 and 212/229 cells. The JSON output includes every candidate's count, each cell's chosen payload and all 78 cells that remain short of complete flipping. Intern-Decision-4B uses the completed MPS/bfloat16 run; interrupted attempts and synthetic responses are excluded.

## Staged code-review demonstration

The fresh review-chain harness builds four temporary Git repositories: a vulnerable release helper, the same helper with injected review-policy comments, a safe change, and a safe change with a legitimate policy note. It passes their diffs to the pinned [jev-review](https://github.com/devagrawal09/jev-review) workflow and then applies the demonstration gate. Fixtures are read as source; the harness does not execute the release helper or its test code.

With Node 24 or newer, Git, npm and an OpenRouter key:

```bash
python scripts/setup_review.py
# Set OPENROUTER_API_KEY in your shell before running.
python scripts/run.py review-chain
python scripts/run.py review-replay --upstream
```

The default is one fresh review per arm. `review-chain --profile confirmation` schedules 50 reviews on each of the four fixed inputs, with a default cap of 3,000 outbound decision requests. Add `--ssh` for the failed-transfer input or `--defended` for local D2 checks before gate action. `REVIEW_RUNS_PER_ARM` controls repetitions in the default profile. `REVIEW_CALL_CAP` defaults to 100 there; skipped reviews are recorded if the remaining budget is too small. Each review may trigger multiple requests. Repeated runs need a new `REVIEW_LOG` filename and `REVIEW_OUT` summary filename.

`review-replay --upstream` runs the pinned reviewer against a local response server. Every request must match an unused saved response, and the resulting report must match the saved findings. It requires the upstream setup, but no OpenRouter key or model weights.

Reports, request logs and temporary repositories go into `output/review-chain/`. The upstream checkout goes into the ignored `experiments/review_chain/vendor/` directory. No upstream source or full saved review log is bundled here.

## Candidate-fix regressions

The 17 cases cover jev-review's heading sanitization and source-file coverage (6), jev-router's override and opt-in paths (6), and fast-jev-compaction's keep, short-text, truncation and scan paths (5). Candidate-fix revisions are pinned in `configs/regressions.json`.

```bash
python scripts/setup_regressions.py
python scripts/run.py regressions
```

The setup downloads the candidate sources and a TypeScript runtime into an ignored `vendor/` directory. The cases make no model calls; they check payload survival and branch behavior, including the remaining gaps. Results go to `output/regressions/results.json`.

## Files

```text
configs/       Backend settings and holdout inputs
data/jev/      Two complete historical Jev API experiment logs
data/candidates/  Twelve-model candidate-call archive and protocol
experiments/   Matrix, defense, candidate-family, holdout and replay runners
samples/       Minimal Choice, staged-review, detector and bypass replay fixtures
scripts/       Entry points, setup helpers, independent recount and offline checks
toolkit/       Model adapters, payloads, logging and defenses
```

This repository contains code, evaluation inputs, minimal replay fixtures, the two named Jev API logs and the candidate-family call archive. Model weights, the remaining historical logs, manuscripts and submission materials are kept outside the release. The `.gitignore` admits the source files, configuration and named data files above; runtime outputs and additional documents stay local.

## License

The toolkit is licensed under Apache-2.0; see [LICENSE](LICENSE). The saved review requests include MIT-licensed upstream question schemas; see [NOTICE](NOTICE) and [licenses/jev-review-MIT.txt](licenses/jev-review-MIT.txt). The bundled SemIf modules use the [MIT license](licenses/SemIf-MIT.txt). Downloaded models and their inference packages retain their upstream licenses.
