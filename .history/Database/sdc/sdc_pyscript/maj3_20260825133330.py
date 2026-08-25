#!/usr/bin/env python3
"""Auto-generated adapter for maj3: Y = majority(A,B,C)."""

from _comb_cell import configure

CELL_ID = "maj3"
INPUTS = ('A', 'B', 'C')
TRUTH_TABLE = (0, 0, 0, 1, 0, 1, 1, 1)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
