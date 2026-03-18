#!/usr/bin/env python3
"""
Opensens Academic Explorer (OAE) — Branded CLI Entry Point
===========================================================
Multi-agent crystal structure prediction and material discovery platform.

Usage:
    python3 oae.py                              # v1 convergence (95% target)
    python3 oae.py --v2                         # v2 convergence (99% target)
    python3 oae.py --rtap                       # RTAP discovery mode
    python3 oae.py --rtap --max-iterations 50   # Extended RTAP run
    python3 oae.py --list-protocols             # List laboratory protocols
    python3 oae.py --protocol discovery         # Run a laboratory protocol
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    # Handle laboratory protocol commands before falling through to run.py
    if "--list-protocols" in sys.argv:
        from laboratory.registry import list_protocols
        protocols = list_protocols()
        print(f"\nOAE Laboratory — {len(protocols)} protocols available:\n")
        for p in protocols:
            print(f"  {p['protocol_id']:25s} {p['name']}")
            print(f"  {'':25s} {p['description'][:70]}")
            print(f"  {'':25s} Material: {p['material_type']}, Stages: {p['n_stages']}")
            print()
        return 0

    if "--protocol" in sys.argv:
        idx = sys.argv.index("--protocol")
        if idx + 1 >= len(sys.argv):
            print("ERROR: --protocol requires a protocol ID")
            return 1
        protocol_id = sys.argv[idx + 1]

        from laboratory.registry import get_protocol
        from laboratory.runner import LabRunner

        protocol = get_protocol(protocol_id)
        if protocol is None:
            print(f"ERROR: Unknown protocol '{protocol_id}'")
            from laboratory.registry import list_protocols
            ids = [p["protocol_id"] for p in list_protocols()]
            print(f"Available: {', '.join(ids)}")
            return 1

        print(f"\nOAE Laboratory — Running protocol: {protocol.name}")
        print(f"  Stages: {', '.join(protocol.stage_names())}")
        print()

        runner = LabRunner()
        result = runner.execute(protocol)

        print(f"\nCompleted: {result['completed_stages']}/{result['total_stages']} stages "
              f"in {result['elapsed_s']:.1f}s")

        # Show result folders
        output_paths = result.get("output_paths", [])
        if output_paths:
            print(f"\n  Result folders:")
            for p in output_paths:
                print(f"    {p}")

        # Show per-stage summary
        print(f"\n  Stage results:")
        for r in result.get("results", []):
            stage = r.get("stage", "?")
            status = r.get("status", "?")
            elapsed = r.get("elapsed_s", 0)
            icon = "OK" if status == "ok" else status.upper()
            extras = []
            if "score" in r:
                extras.append(f"score={r['score']:.4f}")
            if "n_scanned" in r:
                extras.append(f"scanned={r['n_scanned']}")
            if "n_candidates" in r:
                extras.append(f"candidates={r['n_candidates']}")
            if "n_predictions" in r:
                extras.append(f"predictions={r['n_predictions']}")
            extra_str = f" ({', '.join(extras)})" if extras else ""
            print(f"    [{icon:>7s}] {stage:<30s} {elapsed:>6.1f}s{extra_str}")

        print()
        return 0

    from run import run
    return run()


if __name__ == "__main__":
    sys.exit(main())
