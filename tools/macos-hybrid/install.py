#!/usr/bin/env python3
"""Install/refresh the subgroup-free Surface-v4-only backend."""
from __future__ import annotations
import runpy
from pathlib import Path

HERE = Path(__file__).resolve().parent
runpy.run_path(str(HERE / "optimize_surface_v4_only.py"), run_name="__main__")
