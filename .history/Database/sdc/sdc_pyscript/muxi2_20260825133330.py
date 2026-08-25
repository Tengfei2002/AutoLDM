#!/usr/bin/env python3
"""Auto-generated adapter for muxi2: Y = !(S ? B : A)."""

from _comb_cell import configure

CELL_ID = "muxi2"
INPUTS = ('A', 'B', 'S')
TRUTH_TABLE = (1, 1, 1, 0, 0, 1, 0, 0)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
