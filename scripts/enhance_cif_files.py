"""Batch-enhance all crystal structure CIF files with symmetry ops, Wyckoff labels, and bonds.

Reads each crystal_card.json alongside its structure.cif and regenerates
the CIF with full IUCr-compliant content:
  - _symmetry_equiv_pos_as_xyz loop
  - _atom_site_Wyckoff_symbol column
  - _atom_site_occupancy column
  - _geom_bond_* loop
  - _chemical_formula_sum

Usage:
    python3 scripts/enhance_cif_files.py [--dry-run] [--verbose]
"""
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_v.cif.generator import CIFGenerator

logger = logging.getLogger("CIF.Enhance")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STRUCTURES_DIR = PROJECT_ROOT / "data" / "crystal_structures"


def enhance_all(dry_run: bool = False, verbose: bool = False) -> dict:
    """Re-generate all CIF files from crystal cards with enhanced content.

    Returns summary statistics.
    """
    stats = {"total": 0, "enhanced": 0, "skipped": 0, "errors": 0}

    for card_path in sorted(STRUCTURES_DIR.glob("*/crystal_card.json")):
        cif_path = card_path.parent / "structure.cif"
        stats["total"] += 1

        if not cif_path.exists():
            if verbose:
                logger.warning("No CIF file for %s", card_path.parent.name)
            stats["skipped"] += 1
            continue

        try:
            card = json.loads(card_path.read_text())
            enhanced_cif = CIFGenerator.enhance_from_crystal_card(cif_path, card)

            if not enhanced_cif.strip():
                logger.error("Empty CIF generated for %s", card_path.parent.name)
                stats["errors"] += 1
                continue

            if dry_run:
                if verbose:
                    print(f"[DRY-RUN] Would enhance {card_path.parent.name}")
                    # Show first 5 lines of new content
                    for line in enhanced_cif.splitlines()[:8]:
                        print(f"  {line}")
                stats["enhanced"] += 1
            else:
                # Back up original
                backup_path = card_path.parent / "structure_v1.cif"
                if not backup_path.exists():
                    cif_path.rename(backup_path)
                else:
                    # Already backed up from previous run
                    pass

                cif_path.write_text(enhanced_cif, encoding="utf-8")
                stats["enhanced"] += 1

                if verbose:
                    print(f"Enhanced: {card_path.parent.name}")

        except Exception as exc:
            logger.error("Error enhancing %s: %s", card_path.parent.name, exc)
            stats["errors"] += 1

    return stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Batch-enhance CIF files")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without writing files")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    stats = enhance_all(dry_run=args.dry_run, verbose=args.verbose)
    print(f"\nCIF Enhancement Summary:")
    print(f"  Total:    {stats['total']}")
    print(f"  Enhanced: {stats['enhanced']}")
    print(f"  Skipped:  {stats['skipped']}")
    print(f"  Errors:   {stats['errors']}")


if __name__ == "__main__":
    main()
