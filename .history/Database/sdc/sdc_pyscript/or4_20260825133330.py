#!/usr/bin/env python3
"""Auto-generated adapter for or4: Y = A | B | C | D."""

from _comb_cell import configure

CELL_ID = "or4"
INPUTS = ('A', 'B', 'C', 'D')
TRUTH_TABLE = (0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
