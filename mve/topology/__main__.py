"""Offline deterministic fixture generation."""

import argparse
from mve.topology.generator import write_corpus


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    write_corpus(args.output)


if __name__ == "__main__":
    main()
