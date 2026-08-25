#!/usr/bin/env python3
"""Auto-generated adapter for xor2: Y = A ^ B."""

from _comb_cell import configure

CELL_ID = "xor2"
INPUTS = ('A', 'B')
TRUTH_TABLE = (0, 1, 1, 0)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
