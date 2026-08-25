#!/usr/bin/env python3
"""Auto-generated adapter for inv: Y = !A."""

from _comb_cell import configure

CELL_ID = "inv"
INPUTS = ('A',)
TRUTH_TABLE = (1, 0)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
