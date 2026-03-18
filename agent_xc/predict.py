"""Agent XC — End-to-end crystal structure prediction from powder XRD data.

Usage:
    python -m agent_xc.predict --xrd pattern.xy
    python -m agent_xc.predict --xrd pattern.csv --composition "Cu2H8C28N6O8"
"""
import argparse
import json
import logging
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from agent_xc.config import XCConfig, OUTPUT_DIR

logger = logging.getLogger("AgentXC")


@dataclass
class XCResult:
    """Complete Agent XC prediction output."""
    agent: str = "agent_xc"
    version: str = "1.0"
    input_file: str = ""
    wavelength: float = 1.5406
    predictions: list = field(default_factory=list)
    cpcp_predictions: dict = field(default_factory=dict)
    processing_time_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "agent": self.agent,
            "version": self.version,
            "input_file": self.input_file,
            "wavelength": self.wavelength,
            "predictions": [p.to_dict() if hasattr(p, "to_dict") else p
                            for p in self.predictions],
            "cpcp_predictions": self.cpcp_predictions,
            "processing_time_seconds": self.processing_time_seconds,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


class AgentXC:
    """XRD-to-structure prediction agent.

    Pipeline: read XRD -> preprocess -> CPCP feature extraction ->
              CCSG structure generation -> XRD simulation -> Rwp scoring
    """

    def __init__(self, config: Optional[XCConfig] = None):
        self.config = config or XCConfig()
        self.config.ensure_dirs()

    def predict(self, xrd_path: Path, composition_hint: str = None,
                num_candidates: int = None) -> XCResult:
        """Full pipeline: read -> preprocess -> predict -> score -> output.

        Args:
            xrd_path: Path to experimental XRD pattern file.
            composition_hint: Optional chemical formula.
            num_candidates: Number of candidates to generate.

        Returns:
            XCResult with ranked predictions.
        """
        start = time.time()
        n_cand = num_candidates or self.config.num_candidates

        logger.info(f"Predicting structure from XRD: {xrd_path}")

        # Step 1: Read XRD pattern
        from agent_xc.preprocessing.xrd_reader import read_xrd
        pattern = read_xrd(Path(xrd_path))
        pattern.wavelength = self.config.wavelength

        # Step 2: Preprocess
        from agent_xc.preprocessing.noise_filter import savitzky_golay_filter
        from agent_xc.preprocessing.normalizer import preprocess_pattern

        pattern = savitzky_golay_filter(pattern)
        pattern = preprocess_pattern(pattern, self.config.two_theta_range, self.config.step)

        # Step 3: Run XtalNet inference
        from agent_xc.xtalnet_bridge.model_loader import XtalNetModelLoader
        from agent_xc.xtalnet_bridge.inference import XtalNetInference

        loader = XtalNetModelLoader(dataset=self.config.dataset)
        inference = XtalNetInference(loader)
        predictions = inference.predict_from_pattern(
            pattern, composition_hint=composition_hint, num_candidates=n_cand)

        # Step 4: Score predictions via XRD simulation
        scored_predictions = []
        for pred in predictions:
            if pred.structure is not None:
                try:
                    from agent_xc.postprocessing.xrd_simulator import simulate_xrd
                    from agent_xc.postprocessing.match_scorer import compute_rwp, compute_rp

                    sim_pattern = simulate_xrd(pred.structure, pattern.wavelength)
                    rwp = compute_rwp(pattern, sim_pattern)
                    rp = compute_rp(pattern, sim_pattern)
                    pred.confidence = max(0, 1 - rwp)
                    scored_predictions.append((pred, rwp, rp))
                except Exception as e:
                    logger.debug(f"XRD scoring failed for rank {pred.rank}: {e}")
                    scored_predictions.append((pred, 1.0, 1.0))
            else:
                scored_predictions.append((pred, 1.0, 1.0))

        # Sort by Rwp (lower is better)
        scored_predictions.sort(key=lambda x: x[1])

        # Step 5: Write outputs
        output_dir = self.config.output_dir / Path(xrd_path).stem
        output_dir.mkdir(parents=True, exist_ok=True)

        output_predictions = []
        for i, (pred, rwp, rp) in enumerate(scored_predictions):
            pred.rank = i + 1

            # Write CIF if structure exists
            if pred.structure is not None:
                cif_path = output_dir / f"rank_{i+1:03d}.cif"
                try:
                    from agent_pb.io.cif_io import write_cif
                    write_cif(pred.structure, cif_path)
                    pred.cif_path = cif_path
                except Exception:
                    pass

            pred_dict = pred.to_dict()
            pred_dict["rwp"] = round(rwp, 4)
            pred_dict["rp"] = round(rp, 4)
            output_predictions.append(pred_dict)

        processing_time = time.time() - start

        result = XCResult(
            input_file=str(xrd_path),
            wavelength=self.config.wavelength,
            predictions=output_predictions,
            cpcp_predictions={
                "models_available": loader.is_available,
                "dataset": self.config.dataset,
            },
            processing_time_seconds=round(processing_time, 2),
        )

        # Save JSON
        json_path = output_dir / "predictions.json"
        json_path.write_text(result.to_json())
        logger.info(f"Results saved to {output_dir} ({processing_time:.1f}s)")

        return result


def run_agent_xc(xrd_path: Path, **kwargs) -> Path:
    """Top-level entry point matching existing agent pattern."""
    config = XCConfig()
    for k, v in kwargs.items():
        if hasattr(config, k):
            setattr(config, k, v)

    agent = AgentXC(config)
    result = agent.predict(xrd_path, **{k: v for k, v in kwargs.items()
                                         if k in ("composition_hint", "num_candidates")})
    return config.output_dir / Path(xrd_path).stem


def main():
    """CLI entry point: python -m agent_xc.predict"""
    parser = argparse.ArgumentParser(
        description="Agent XC — Crystal Structure Prediction from Powder XRD")
    parser.add_argument("--xrd", required=True,
                        help="Path to XRD pattern file (.xy, .csv, .dat)")
    parser.add_argument("--composition", default=None,
                        help="Optional composition hint, e.g., 'Cu2H8C28N6O8'")
    parser.add_argument("--num-candidates", type=int, default=10,
                        help="Number of structure candidates (default: 10)")
    parser.add_argument("--dataset", default="hmof_100",
                        choices=["hmof_100", "hmof_400"],
                        help="XtalNet checkpoint dataset (default: hmof_100)")
    parser.add_argument("--wavelength", type=float, default=1.5406,
                        help="X-ray wavelength in Angstrom (default: 1.5406 Cu Ka1)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = XCConfig(
        dataset=args.dataset,
        wavelength=args.wavelength,
        num_candidates=args.num_candidates,
    )

    agent = AgentXC(config)
    result = agent.predict(Path(args.xrd),
                           composition_hint=args.composition,
                           num_candidates=args.num_candidates)

    print(f"\n{'='*60}")
    print(f"Agent XC — Prediction Results from {args.xrd}")
    print(f"{'='*60}")
    print(f"Processing time: {result.processing_time_seconds:.1f}s")
    print(f"\nTop predictions:")
    for pred in result.predictions[:5]:
        p = pred if isinstance(pred, dict) else pred
        print(f"  #{p.get('rank', '?')}: {p.get('composition', 'N/A')}, "
              f"SG={p.get('space_group', '?')}, "
              f"Rwp={p.get('rwp', 'N/A')}")


if __name__ == "__main__":
    main()
