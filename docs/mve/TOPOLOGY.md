# WP-10 offline topology grammar v1

This packet has its own immutable `mve-oriented-pd-v1` representation. It does
not construct Euclidean observations, authorize assumptions, activate a classifier,
or claim G5. `Q-topo-workflow` keeps its existing P5, human-labelled choices
`pd_transcribe`, `invariants_only`, `reject_diagram`, `human`; this packet produces
no training labels for that question. §7 step 10's domain separation is retained.

## Frozen conventions

Coordinates are exact integers/rationals in a Cartesian plane (y increases up).
The visible side has normal +z. Components are closed piecewise-linear strands,
traversed counter-clockwise: positive signed polygon area. Zero/negative area,
zero-length edges, backtracking, distinct-strand tangencies, endpoint touches,
collinear overlaps and triple crossings are rejected, not repaired. Ordinary
adjacent polygon vertices are allowed. The supported domain is 1–4 components
and 0–7 transverse double crossings. This is a deliberately restricted grammar;
zero signed area is unsupported even when some broader convention could decode it.

“Lowest-leftmost” means lexicographic `(y, x)`. Choose the component at its lowest
crossing, choosing its underpass first when both visits belong to it. Number its
incoming arc 1, then follow that component counter-clockwise and number each next
arc at each crossing visit. Choose remaining components by their lowest crossing
(underpass breaks a shared-crossing tie); continue contiguous labels. Crossing-free
components come last in their source order and each receive one singleton arc.
This explicit circle convention distinguishes an unknot from a two-component
unlink even though both have empty PD lists. Each crossing arc occurs twice in PD.

Order crossing rows by `(y, x)`. A PD row starts at the **incoming underpass**
half-arc, then lists the four outward half-arcs counter-clockwise. Opposite slots
continue the same strand: slots 0/2 are under, 1/3 over. Never join under and over.
The right-handed sign is `sign(det(t_over, t_under))`: +1 precisely when the
ordered tangents followed by +z form a right-handed frame. In this coordinate
recipe a left-top-to-right-bottom overpass has sign −1. For sign +1 the successors
are `row[0]→row[2]`, `row[3]→row[1]`; for −1 they are `row[0]→row[2]`,
`row[1]→row[3]`. Stored component cycles and signs must reproduce these successors.

Mirroring is an x-reflection, followed by reversing each traversal to restore
counter-clockwise direction; `mirror: true` records that transformation. It is
never silently undone for scoring. The mirror flag is provenance; PD scores compare
PD, and component correctness is separately counted. A false mirror flag on an
otherwise identical supplied PD does not change the exact-PD score.

## Generator and coordinate decoder

`python3 -m mve.topology --output /tmp/mve-wp10` writes 30 PNGs (512×512), exact
geometry including gap intervals, exact PD truth, a recipe/class manifest, a
frozen split and a hashed receipt. No model, image-learning code, network call or
download is involved. Pillow 12.2.0 is already installed and pinned in `DEPS.lock`.
The raster recipe is black width-3 lines on white, no antialiasing/fonts, PNG
compression 9. Pixel y is flipped only at render time. Deterministic PNG bytes
are promised under the locked local Python/Pillow/zlib versions.

The five construction families are closed braids:

| Family | Strands | Signed braid word |
| --- | --- | --- |
| unknot | 1 | empty |
| trefoil | 2 | 1, 1, 1 |
| figure-eight | 3 | 1, −2, 1, −2 |
| Hopf link | 2 | 1, 1 |
| two-component unlink | 2 | empty |

Each has base, mirror, positive/negative R1 stabilization, R2 insertion and
near-miss variants. R1 adds an outer strand and one last generator ±n; R2 appends
1,−1. For the one-strand unknot, R2/near-miss first use one R1 stabilization so
there are two strands. A near miss moves two strands to within 1/8 exact coordinate
unit without intersection, then separates them. Raster strokes may merge at that
resolution: this is an intentionally hard future perception control, not evidence
of pixel recovery. Chiral trefoils share a family and remain in the same partition;
the class vocabulary distinguishes `trefoil_negative` and `trefoil_positive` by
the sign of their three-crossing representative. The other four class names are
unoriented knot/link types. Labels are construction truth, not inferred invariants.

Symbolic braid events specify truth crossing locations and over/under edges.
The decoder independently enumerates rational segment intersections and determines
which passage is under from a strictly interior gap interval. Exactly one gap must
cover exactly one crossing; missing, double, reused or orphan gaps are ambiguous.
The image renderer cuts precisely those intervals; it never erases a whole crossing.
Both routes share the deterministic arc-numbering/PD assembler, so the agreement
is **self-consistency**, not an independent transcript test. Hand-numbered PD tests
also pin the base trefoil, figure-eight and Hopf examples.

`mve.evaluation.splits.freeze` supplies all five existing partition names, one
family per partition; every variant remains with its family. Since all 30 public
fixtures are used in development, the frozen split is **retired for evaluation**,
with its parent hash retained. It must not be reused to establish G5. A future
sealed corpus needs new families/items and independent image perception, plus a
separate permitted-external set. Geometry/truth artifacts must be isolated from
that future inference process; this packet makes no gold-isolation claim for its
coordinate decoder.

## Scores and error accounting

Exact = identical ordered PD lists, literally. Canonicalized = equality under
cyclic shifts of labels **within each oriented component** and component reordering
only. Canonicalization enumerates that finite orbit. It does not reorder crossing
rows, reverse components, rotate local crossing slots, reflect mirrors, or apply
Reidemeister moves. R1/R2 controls of the same knot therefore fail transcript
identity. Component counts remain separate; `complete` additionally requires the
correct count, so two empty lists do not conflate an unknot and an unlink.

PD exact/canonicalized/complete scores have diagrams as denominator. Crossing
micro pools correctly matched indexed rows over all gold crossings. Crossing macro
averages each diagram's matched fraction, excluding zero-crossing diagrams with
that exclusion count explicit. Complete scores still include crossing-free cases.
Orientation micro/macro use the same denominators; signs are compared only when
the indexed crossing's opposite arc pairs establish fixed correspondence.
Unaligned or malformed/missing predictions contribute no matches and remain in
the denominators. Sign agreement without arc correspondence is not scored as
orientation success. Crossing count errors and component correctness are separate.

The general PD null is N/A. Conditional complete orientation has null `2^(-c)`
per gold diagram, with its sample mean; `c=0` is the vacuous value 1. That null
assumes already fixed crossings and correspondence, and is not an unconditional
transcription baseline. Knot-type nulls are `1/k` using the observed class vocabulary
and the actual majority fraction. Type predictions are separate optional inputs;
none are supplied by the self-consistency run (all are unknown, retained in the
denominator). Missing invariants have denominator 0 and value null, not agreement.
All counts are descriptive, without population confidence intervals.

The exact taxonomy is `{skeleton, crossing_detection, orientation, traversal,
arc_association, labels, canonicalization, unsupported_convention,
ambiguous_source, unresolved}`. Decoder refusals carry one of these categories;
missing/malformed PD predictions are unresolved. No classifier decides knot type.

## Optional operations and first certificate

SnapPy and Spherogram are absent locally; no package was installed. The returned
operation receipts name `snappy.Link(pd)` (construction validity),
`Link.exterior().identify()` (candidate identification, never truth) and
`Link.jones_polynomial()` (invariant consistency) exactly, with status unavailable.
These are explicit placeholders, not implemented SnapPy adapters. A later adapter
must pin the dependency/convention and preserve crossing-free component metadata;
constructing from an empty PD list alone loses that metadata. No invariant result
is asserted here, nor can invariant agreement verify a picture transcript.

`certificate()` reads the opposite-strand successor map from a validated diagram,
checks that its orbit contains every arc, and emits a concrete Lean theorem that
iterating the successor enumerates all arcs once and returns to the start. Multiple
components are refused. `check_certificate()` uses the existing SHA-pinned Lean
4.29.0 binary directly with core `Init`, `--stdin`, a minimal environment and a
30-second timeout. It invokes no Lake, imports, package build or download. `by decide`
is kernel checked and `#print axioms` must report none; no `sorry`, `axiom`,
`native_decide` or external oracle is used. The certificate is about **the decoded
combinatorial record only**. It proves neither image transcription nor knot type.

The receipt is consumed by `mve.reporting` as a separate self-consistency table.
G5's grammar criterion can be evidenced; its synthetic/external perception and
perception-score criteria remain unknown. The adapter cannot turn this receipt
into a G5 pass, even when its exact and canonicalized scores equal 100%.
