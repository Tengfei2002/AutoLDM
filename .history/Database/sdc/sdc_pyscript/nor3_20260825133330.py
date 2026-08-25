#!/usr/bin/env python3
"""Auto-generated adapter for nor3: Y = !(A | B | C)."""

from _comb_cell import configure

CELL_ID = "nor3"
INPUTS = ('A', 'B', 'C')
TRUTH_TABLE = (1, 0, 0, 0, 0, 0, 0, 0)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
