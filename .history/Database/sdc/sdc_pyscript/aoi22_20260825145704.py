#!/usr/bin/env python3
"""Auto-generated adapter for aoi22: Y = !((A & B) | (C & D))."""

from Database.sdc.sdc_pyscript._comb_cell import configure

CELL_ID = "aoi22"
INPUTS = ('A', 'B', 'C', 'D')
TRUTH_TABLE = (1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 0, 0, 0, 0)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
