# Math Vision Engine (MVE) — Review of Sources

Date: 2026-09-27. Companion to `MVE_PLAN.md`. Every fact below was collected from the
primary page (arXiv HTML, GitHub README, HF card, vendor docs) by research agents on
2026-09-27. Items the agents could not confirm from a primary page are marked
**unverified**. Nothing was cloned or executed.

Verdict scale: **Adopt** (use the artifact as-is or with a thin wrapper), **Adapt**
(take the design or a component, rewrite the rest), **Cite** (idea only, nothing
reusable released).

## 0. Summary table

| Source | What it is | Released | Verdict for MVE | Why |
|---|---|---|---|---|
| MultiMath, arXiv 2409.00147 | LLaVA-style 7B on DeepSeekMath-RL + MultiMath-300K (K-12, one image each, zh/en captions + GPT-4o step solutions) | Weights (7B), dataset 5.9 GB, eval scripts; no training/RL code | **Adapt** (caption prompt, step format, eval harness) | Free-prose captions, no formal output, unmaintained since 2025-01 |
| GeoX, arXiv 2412.11863 (ICLR 2025) | Geo-ViT (MAE on 120K diagrams) + GS-Former + Geo-LLM-7B → operator program → SymPy | Weights on HF, code Apache-2.0, alignment data 6,232 images; instruction data by email | **Adapt** (diagram-encoder lesson, formal-caption objective, execute-and-compare reward) | Output is a numeric calculator program, not propositions; caption grammar = only `Line` and `lieson` circle; provenance of alignment data disputed (issue #5); HF artifacts unlicensed |
| Geo-LLaVA, arXiv 2412.10455 | LLaVA-1.5-13B + retrieval-augmented meta-training on GeoMath (solid geometry, ~10K, zh→en) | Nothing found | **Cite** (describe-then-solve; retrieval of analogous worked diagrams) | No code, no data; SOTA claim contradicted by its own table |
| Euclid, arXiv 2412.08737 (the paper the request most likely meant by "synthetic visual descriptions") | Geoperception benchmark + synthetic image engine driven by AlphaGeometry's premise language + ConvNeXt perception model with curriculum | Code Apache-2.0, Geoperception 11,657 rows Apache-2.0, weights on HF | **Adopt** (image engine as ground-truth generator; Geoperception as perception unit test; ConvNeXt+small-LLM as a cheap perception head) | Only 7 predicates, single diagram style, single-predicate QA rather than full-diagram records |
| MathGLM-Vision, arXiv 2409.13729 | GLM-4V-9B / CogVLM2-19B / 32B SFT on MathVL (487K, 85% geometry, GPT-4o solutions) | 9B and 19B weights; MathVL and 32B not released | **Adapt** (reasoning backbone; five-way error taxonomy; VQA-mixing recipe) | Training data unreleased; vision-recognition errors only 11.4% by their own coarse taxonomy, which cannot separate "misread" from "misdeduced" |
| Jev (TypeSafe AI; video TDeNkF4cElg; aiblewmymind) | Text-only "System One" decision model: Choice / Score / Noul primitives with calibrated probabilities | Hosted API (`jev-1.13.0`); open-weight look-alikes: openjev/openjev 27B (CC BY-NC, takes one screenshot), heman10x/openJev-verdict 151M (Apache-2.0, text only, installed locally) | **Adopt as the classification layer, never as a truth judge** | arXiv 2609.26550: within 3 points of the best LLM judge at 0.36% of the fee, but weakest on derivation checking and polished wrong answers; gap concentrated in low-confidence decisions, so the cascade recovers 99% |

## 1. MultiMath (pengshuai-rin/MultiMath)

- Authors: Peng, Fu, Gao, Zhong, Fu, Tang (PKU / ByteDance / UESTC), Aug 2024.
  https://arxiv.org/html/2409.00147v1 · https://github.com/pengshuai-rin/MultiMath ·
  https://huggingface.co/datasets/pengshuai-rin/multimath-300k
- Architecture: CLIP ViT-L/14-336 → 2-layer MLP → DeepSeekMath-RL-7B. Four stages:
  alignment (adapter only), vision instruction tuning, math instruction tuning
  (MultiMath-300K + Geo170K-QA + MathV360K), PPO with a step-level reward model. PPO
  hyperparameters and sample counts **unverified** (not in the HTML).
- Data: 298,670 problems, 290,227 train / 8,443 val, from Xuekubao's K-12 bank under
  purchased rights. LLaVA `conversations` JSON. Caption prompt: LaTeX OCR if the image is
  a formula, else "describe so the graphic can be accurately drawn" (rays, angle values,
  bisectors). Solution prompt: `Step X (theorem/basis): …` lines and `Answer: \boxed{}`;
  three GPT-4o rounds (generate → revise → verify against gold; keep only correct).
- Results: MathVista 50.0 (GPT-4V 49.9), MathVerse 40.1 (GPT-4V 43.1); MathVerse
  vision-only subset 15.0, the weak spot. RL helped text benchmarks, hurt MathVerse.
- Repo: Apache-2.0, 8 commits, last push 2025-01-22, HF loading bug (issue #4), no
  per-domain labels (issue #3), dataset license field empty (**unverified** redistribution).
- Reusable for MVE: the caption prompt as a seed for the observation stage; the justified
  step format as an intermediate representation before Lean tactics; the
  MathVista/MathVerse scoring scripts; the generate/revise/verify data-cleaning template.
- Missing: any formal output, parsed primitives, topology, proof-level tasks, reward code.

## 2. GeoX (InternScience/GeoX)

- https://arxiv.org/html/2412.11863v2 · https://github.com/InternScience/GeoX ·
  https://huggingface.co/U4R/GeoX · https://huggingface.co/datasets/U4R/GeoX-data
- Thesis: pretrain on *formal* descriptions (`Line A E D`, `\odot O lieson A C D B`) and
  formal solution programs instead of natural-language captions; diagrams are sparse so
  most patches are noise.
- Geo-ViT: ViT-B/16, MAE mask 0.75, 800 epochs, 120K+ diagrams (`main/train_encoder.py`;
  the README path `pretrain/pretrain_encoder.py` does not exist). Geo-LLM-7B: LLEMMA-7B
  continued on ~100M geometry tokens (corpus not released, issue #9). GS-Former: Q-Former
  with a Geo-aware Query Generator and a Semantics-guided Geometry Sampler (progressive
  Gumbel-softmax patch masking, sparsification loss). Ablation on Geometry3K completion:
  48.6 → 57.4 (+GQG) → 58.6 (+SGS).
- Output: an operator token stream (`gougu_minus 5.0 V_0`, `PRK_Perim …`) executed by
  `solver/eval_equ.py` with SymPy under a 2 s timeout; correct if |pred−tgt| < 5e-3.
  "Verification" is execute-and-compare, never deductive. UniGeo "proof" is a proving
  program checked by string match.
- Results: GeoQA 54.9 (GPT-4V 43.4), Geometry3K completion 58.6 (PGPSNet 48.1),
  PGPS9K 52.7, MathVista-GEO 72.6 (GPT-4o 66.1). Solver-free GeoQA 67.4 vs MAVIS 66.7:
  the formal-pretraining margin is small in that setting.
- Repo: Apache-2.0, 37 commits, last push 2025-01-25, 11 open issues with zero maintainer
  replies (load errors #11/#12), torch 2.0.1 / transformers 4.36.2 era. PGPS9K's author
  states in issue #5 that the alignment data and scheme come from PGPS9K; HF cards carry
  no license.
- Reusable for MVE: the domain-gap finding (CLIP encoders fail on line drawings); the
  formal-caption alignment objective, which is exactly "structured diagram observations";
  the SGS idea for sparse diagrams; execute-and-compare as a cheap reward.
- Missing: parallel/perpendicular/angle/length/tangency/betweenness predicates; propositions
  or proof terms; Lean; a repair loop; a clean license.

## 3. Geo-LLaVA (arXiv 2412.10455)

- Xu, Luo, Shi (Huawei Singapore), LGM3A '24 workshop at ACM MM. No code or data found.
- LLaVA-1.5-13B + ViT-L/14 + BERT retriever; LoRA SFT on image-context pairs → QA →
  meta-training with K=5 retrieved exemplars. GeoQA+ 65.25 / GeoMath 42.36; G-LLaVA-13B
  is at 67.00 in the same table.
- Only transferable signal: image-context description pairs gave the largest single gain on
  solid geometry (+8.5), so "describe, then solve" is worth keeping as an explicit stage.

## 4. Euclid (arXiv 2412.08737) and Geoperception

- Zhang, Liu, Yu, Hu, Neiswanger (USC; other affiliations **unverified**), ICLR 2025
  workshop. https://github.com/euclid-multimodal/Euclid (Apache-2.0) ·
  https://huggingface.co/datasets/euclid-multimodal/Geoperception (Apache-2.0, 11,657 rows:
  id, question, answer, predicate, image).
- Engine: shapes written in AlphaGeometry's premise language
  (`A B C = triangle A B C; D = midpoint B C`), validity checked and coordinates sampled by
  AlphaGeometry, rendered by its matplotlib drawing code (**inferred**). Primitives: points,
  lines, circles, midpoints, intersections, bisectors, tangents; predicates parallel,
  perpendicular, equal. ~1.6M templated QA instances in three difficulty stages.
- Model: ConvNeXt-Large/XXLarge@512 (CLIP-pretrained, frozen) + MLP + Qwen2.5-1.5B.
- Geoperception averages: random 16.4, Qwen2-VL-7B 40.6, GPT-4o 49.7, Claude 3.5 Sonnet
  51.3, Gemini-1.5-Pro 57.0, Euclid-XXL 67.9. PointLiesOnLine: Euclid-XXL 83.0 vs
  Gemini-1.5-Pro 24.4. Annotation-dependent relations (parallel, perpendicular, equal with
  tick marks) stay hard for every model.
- Insights: CNN encoders learn geometry faster than 3–5× larger ViT/CLIP/SigLIP; freezing
  the encoder costs nothing; scaling the LLM past 1.5B does not help; easy→hard curriculum
  converges fastest; synthetic-only training transfers to textbook diagrams.
- Reusable: the image engine as the ground-truth generator (extend to emit the full
  predicate set per diagram and add tick/arc/arrow styles); Geoperception as the perception
  regression test; ConvNeXt + small LLM as a cheap local perception head.

## 5. MathGLM-Vision (arXiv 2409.13729)

- Yang et al. (Tsinghua, Beihang, Zhipu.AI). https://github.com/THUDM/MathGLM-Vision.
  9B and 19B weights released; 32B, MathVL and MathVL-test not released. License
  **unverified**.
- MathVL: 145,568 open-source samples re-solved by GPT-4o + 341,346 Chinese K-12 problems;
  geometry 85.5%. Single SFT stage, encoder at 0.1× LR, mixed with 19 VQA datasets
  (removing the mix drops MathVista 52.2 → 41.3).
- MathVista testmini: 9B 52.2, 19B 61.1, 32B 62.4 (GPT-4o 63.8). Error analysis on
  MathVL-test: reasoning 69.1%, knowledge 12.7%, vision recognition 11.4%, calculation 4.3%.
- Reusable: released backbone; the error taxonomy as a coarse eval; VQA mixing to keep
  perception. Not reusable: the data, any perception tests, any formal language.

## 6. Jev

Verified from vendor docs and independent write-ups:

- TypeSafe AI "System One" decision model, announced 2026-09-15; API model `jev-1.13.0`.
  Input is a `state` (string / JSON / array) plus typed questions answered in parallel.
  Primitives: **Choice** (≤255 options → choice + full probabilities + confidence),
  **Score** (2–10 ordered levels), **Noul** (yes/no probability). It never generates text.
  https://docs.typesafe.ai/primitives/choice · https://docs.typesafe.ai/models ·
  https://docs.typesafe.ai/confidence
- **Text only**: "No image, audio, or video input." 64k context per request.
  $0.042 per MTok input, output free, 70–500 ms. Closed weights, API key only.
- Independent evidence: arXiv 2609.26550, "JEV-as-a-Judge: Accept When Confident, Escalate
  When Unsure" (2026-09-22). Within 3 points of the strongest LLM judge at 0.36% of its fee;
  larger gaps "when judgments require checking a derivation or resisting an elaborately
  written wrong answer"; the gap sits in low-confidence decisions; a frozen cascade keeps
  99% of the comparator's accuracy.
- Open-weight look-alikes (name collision): `openjev/openjev` 27B (CC BY-NC 4.0, text plus
  one screenshot, 84.0% vs hosted 85.4% self-reported); `heman10x/openJev-verdict` 151M
  ModernBERT/GLiClass (Apache-2.0, text only, 512-token cap) which is what
  `~/Developer/Opensens/models/openjev/` holds (model_fp16.onnx 303,785,047 bytes).
- Video TDeNkF4cElg: title "Breaking: Jev Plays Mario — And Grades Itself (94% Correct)",
  channel "AI Security Dispatch". The 94% figure is **unverified** anywhere else.
- aiblewmymind.substack.com has one Jev post (2026-09-24, "15 Ways to Use It Without
  Code"). The two infographics in the request ("3 ways to use Jev", "When to use Jev, an
  LLM, or both") were **not found** there; the decision tree they draw matches the consensus
  tree in the TypeSafe, LangChain and OpenRouter write-ups: code if computable; Jev if the
  answer list is known in advance and the evidence is in the state (add `other`); LLM if
  words, arithmetic or a derivation are needed; cascade when bounded but high-stakes.
- Threshold discipline: "a confidence threshold is not one number", tier by risk; start
  conservative, fit on your own held-out data; audit a fixed sample of confident answers.

Local harness state (read-only survey of `~/Developer/Opensens/rh-jev-harness`, HEAD
`de9f54e`): backends TypeSafe / Rule / Replay / OpenJev; routers `policy_manager`,
`policy_worker`, `policy_compact`, `policy_fleet`, `dream`; 308 tests pass; the TypeSafe
endpoint and wire format in `rhjev/backends.py` are assumptions; `~/.jev-router.env` is
absent so nothing makes a network call; Dream Pilot 1 ran D-rule and S only (no key) with
0 of 33 approvals in any arm. The 151M openJev cannot fit a 300-word state (0/160 prompts),
so any state handed to it must stay under about 140 words.

## 7. Landscape beyond the six sources (short list; full table in the agent survey)

Adopt: Newclid (DDARN, reads GeoGebra `.ggb`, `pip install newclid`), LeanGeo (MIT, 260
theorems, `esmt` tactic, LeanGeo-Bench 122), LeanEuclid (MIT, system E, E3 statement
equivalence), Draw2Think (Propose-Draw-Verify on a GeoGebra kernel, 95.9% predicate level,
license **unverified**), ProofWidgets4 + Penrose (render a Lean statement back into a
picture inside the infoview), Goedel-Prover-V2 8B/32B (Apache-2.0), DeepSeek-Prover-V2 7B,
Geoperception / VisOnlyQA / MathGlance / GeoBench / KnotBench (evals), SnapPy (GPL-2+,
knot and 3-manifold verifier), JSXGraph (LGPL/MIT dual, commercial-safe canvas; GeoGebra
apps are non-commercial without agreement).

Adapt: AlphaGeometry2 DDAR (checker for observation records, needs coordinates), MechGeo's
GeoIR intermediate representation and deterministic Lean translation (arXiv 2608.02295,
code URL not found), Euclean's four-stage repair loop and Numina-Geometry 177,597 (arXiv
2607.19374), Inter-GPS 91-predicate vocabulary (MIT), PGDP5K/PGDPNet primitive extractor
(MIT code, gated data), DeTikZify (sketch→TikZ round trip), DeepSeek-OCR-2 (labels).

Vision models (verified on api-docs.deepseek.com on 2026-09-27): **DeepSeek-V4.1-Flash**
(`deepseek-flash`, 552B MoE, native image input, 1M context, MIT weights, $0.30/$1.20 per
MTok peak, $0.15/$0.60 off-peak). **DeepSeek-V4-Pro: image input "Not supported"**, so it
is a text-only judge. Claude and GPT vision docs both concede approximate localisation and
inexact counting; they serve as disagreement judges, not primary perceivers.

Five evidence-backed VLM failure modes on geometry: (1) near-zero fine-grained grounding and
"blind faith in text" (MathGlance); (2) perception, not reasoning, is the bottleneck, and
reasoning RL cannot recover from a wrong parse (VisOnlyQA, GeoPQA); (3) diagram→symbol
transcription collapses (KnotBench: 0/100 strict PD codes from images; move prediction
32.5% from image vs 88% from PD code); (4) shape and relation confusion, small-detail loss;
(5) long chains of thought from a wrong parse compound the error (GeoBench).
