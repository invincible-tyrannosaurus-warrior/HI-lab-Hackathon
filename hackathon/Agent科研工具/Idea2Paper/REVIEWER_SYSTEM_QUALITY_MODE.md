# Reviewer System Quality Mode (Blind + τ-Calibrated)

This document describes how to run the new reviewer in **quality mode** and how to calibrate `τ`.

---

## 1) Quality Mode Flags

Recommended environment variables:

```
export I2P_CRITIC_STRICT_JSON=1
export I2P_CRITIC_COACH_ENABLE=1
export I2P_JUDGE_TAU_PATH="Paper-KG-Pipeline/output/judge_tau.json"
```

Optional tuning:

```
export I2P_TAU_METHODOLOGY=1.0
export I2P_TAU_NOVELTY=1.0
export I2P_TAU_STORYTELLER=1.0
```

---

## 2) τ Calibration (Offline)

Script:

```
python Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py \
  --role Methodology --pairs 2000
```

Repeat for each role:

```
python Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py --role Novelty
python Paper-KG-Pipeline/scripts/tools/fit_judge_tau.py --role Storyteller
```

Output:
- `Paper-KG-Pipeline/output/judge_tau.json`
- `Paper-KG-Pipeline/output/judge_pairs.jsonl`

If you change **rubric**, **card schema**, or **LLM judge model**, you must re-fit τ.

---

## 3) Blind Judge Guarantees

- LLM never sees real scores, titles, authors, or paper_id.
- LLM never outputs 1–10 scores.
- All scoring is deterministic from anchors + fixed τ.

---

## 4) Fallbacks

If strict JSON is disabled (`I2P_CRITIC_STRICT_JSON=0`), the judge will fall back to neutral comparisons to keep the pipeline moving (use only for smoke tests).
