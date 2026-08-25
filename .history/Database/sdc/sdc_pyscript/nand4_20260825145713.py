#!/usr/bin/env python3
"""Auto-generated adapter for nand4: Y = !(A & B & C & D)."""

from Database.sdc.sdc_pyscript._comb_cell import configure

CELL_ID = "nand4"
INPUTS = ('A', 'B', 'C', 'D')
TRUTH_TABLE = (1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
