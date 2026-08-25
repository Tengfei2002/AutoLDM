#!/usr/bin/env python3
"""Auto-generated adapter for xnor2: Y = !(A ^ B)."""

from Database.sdc.sdc_pyscript._comb_cell import configure

CELL_ID = "xnor2"
INPUTS = ('A', 'B')
TRUTH_TABLE = (1, 0, 0, 1)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
