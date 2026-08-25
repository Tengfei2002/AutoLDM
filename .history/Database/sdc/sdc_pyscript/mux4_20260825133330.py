#!/usr/bin/env python3
"""Auto-generated adapter for mux4: Y = D[S1:S0]."""

from _comb_cell import configure

CELL_ID = "mux4"
INPUTS = ('D0', 'D1', 'D2', 'D3', 'S0', 'S1')
TRUTH_TABLE = (0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 0, 1, 0, 0, 0, 1, 1, 0, 1, 1, 0, 0, 1, 1, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1, 1, 0, 0, 1, 1, 0, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 1, 1, 0, 1, 1, 1, 1)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
