# Phase 6: NLP Baselines

**Goal (roadmap):** measurable text-similarity baselines, scored by exactly the same harness as the
rule pipelines. They are rows A (keyword) and B (embedding) of the plan §21 ablation study.

## What was built

| Component | Module |
|---|---|
| Text views: comment (cleaned) vs. **added code** (commented file + changed tests; comments kept on purpose) | `semantic/text.py` |
| A. **Lexical**: share of the comment's content words found in the added code (identifiers split: `total_price` → total, price) | `semantic/scorers.py` |
| B. **TF-IDF** + cosine, vectorizer fitted on the **dev corpus only** (scikit-learn) | `semantic/scorers.py` |
| C. **Sentence embeddings** + cosine: `sentence-transformers/all-MiniLM-L6-v2`, CPU | `semantic/scorers.py` |
| Similarity verifier: no added code → NOT_SATISFIED; else score ≥ τ → SATISFIED, else NOT_SATISFIED (cites its score as evidence) | `semantic/verifier.py` |
| Common harness: a `Verifier` protocol; `evaluate()` scores rule pipelines and baselines identically | `evaluation/runner.py` |
| Tuning + reporting: threshold on dev only, applied unchanged to held-out; ROC-AUC; git commit recorded | `evaluation/baselines.py` |

Dependencies: scikit-learn is in the `dev` group (CI tests TF-IDF). sentence-transformers and
PyTorch (CPU) are in the optional `nlp` group, **not** in the service image (checked: image has
neither) or CI.

## Protocol

1. Fixed before the first run: fit on dev, **tune τ on dev for 4-class accuracy**, evaluate dev and
   held-out with τ frozen.
2. Added after the first run, reported separately: the accuracy criterion made every baseline
   collapse to **"always NOT_SATISFIED"** (the majority class). That is a real result, but it hides
   whether the scores carry any signal. So we also report **ROC-AUC** (valid = gold SATISFIED vs.
   invalid = gold NOT / PARTIALLY; UNCERTAIN excluded) and a **balanced operating point** (Youden's J,
   tuned on dev, frozen for held-out).

## Results

`uv run --group nlp verireview eval-baselines` (report: `experiments/phase6_baselines.json`; dev
hash `1754164a4b78…`, held-out hash `d5a64d31c46e…`):

```text
verifier                      set           acc    mF1    FAR    FBR  threshold
lexical [accuracy-tuned]      dev         0.448  0.155  0.000  1.000  0.833
lexical [accuracy-tuned]      held-out    0.292  0.137  0.000  0.929  0.833
lexical [Youden]              dev         0.379  0.220  0.722  0.250  0.174
lexical [Youden]              held-out    0.542  0.191  0.875  0.071  0.174
tfidf [accuracy-tuned]        dev         0.448  0.155  0.000  1.000  0.721
tfidf [accuracy-tuned]        held-out    0.333  0.170  0.000  0.857  0.721
tfidf [Youden]                dev         0.379  0.217  0.444  0.500  0.284
tfidf [Youden]                held-out    0.500  0.271  0.250  0.500  0.284
embedding [accuracy-tuned]    dev         0.448  0.155  0.000  1.000  0.730
embedding [accuracy-tuned]    held-out    0.333  0.170  0.000  0.857  0.730
embedding [Youden]            dev         0.414  0.242  0.500  0.250  0.469
embedding [Youden]            held-out    0.542  0.255  0.750  0.214  0.469
rules (mvp)                   dev         1.000  1.000  0.000  0.000  -
rules (mvp)                   held-out    0.875  0.867  0.000  0.071  -
ROC-AUC, valid vs invalid resolution (0.5 = no signal):
  lexical      dev 0.406   held-out 0.674
  tfidf        dev 0.396   held-out 0.558
  embedding    dev 0.465   held-out 0.688
```

FAR = false acceptance (an invalid resolution accepted); FBR = false blocking (a valid one rejected).

## Findings

1. **No usable signal on the dev set.** AUC is below 0.5 for all three: invalid resolutions score
   *higher* than valid ones. The dev set is rich in lexical traps (a comment, TODO or docstring that
   repeats the reviewer's words), which a similarity measure rewards. A unit test demonstrates it:
   `# TODO: validate username` scores 0.5 lexical overlap with "Validate `username` before saving."
2. **Some signal on held-out (AUC 0.56–0.69), but not safely usable.** Every threshold that accepts
   anything also accepts bad fixes: 25–88% false acceptance on held-out, versus **0%** for the rules.
3. **Embeddings ≈ lexical overlap here.** The pretrained sentence model adds little over word overlap
   for "comment vs. code". It is not trained to judge whether code satisfies a request.
4. **Structurally blind:** a similarity score cannot output PARTIALLY_SATISFIED or UNCERTAIN.

This supports the plan's design principle (§2: not "comment + diff → model → SATISFIED"). It is
evidence from small, author-written sets, not proof: roughly 20 valid-vs-invalid cases per set give
wide uncertainty on AUC. Bootstrap confidence intervals and the full ablation are Phase 10.

## What this means for Phase 7

A code-aware model (e.g. CodeBERT) should be used as **one evidence source** for what rules cannot
decide (the UNCERTAIN / inconclusive cases), not as a verdict. Any semantic evidence must be scored
with the same harness and must not raise the false-acceptance rate above 0 on held-out.

## Commands

```bash
uv sync --group nlp                                  # sentence-transformers + PyTorch (CPU)
uv run --group nlp verireview eval-baselines --out experiments/phase6_baselines.json
uv run verireview eval-baselines --scorers lexical,tfidf   # without the heavy group
uv run --group nlp pytest -m model                   # real-model test (downloads MiniLM once)
```
