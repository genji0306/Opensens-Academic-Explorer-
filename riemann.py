#!/usr/bin/env python3
"""Compatibility wrapper for the Riemann CLI."""
from __future__ import annotations

import sys

from riemann.cli import main


if __name__ == "__main__":
    sys.exit(main())
