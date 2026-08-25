#!/usr/bin/env python3
"""Auto-generated adapter for nand3: Y = !(A & B & C)."""

from _comb_cell import configure

CELL_ID = "nand3"
INPUTS = ('A', 'B', 'C')
TRUTH_TABLE = (1, 1, 1, 1, 1, 1, 1, 0)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
