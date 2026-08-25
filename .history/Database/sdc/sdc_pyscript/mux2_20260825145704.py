#!/usr/bin/env python3
"""Auto-generated adapter for mux2: Y = S ? B : A."""

from Database.sdc.sdc_pyscript._comb_cell import configure

CELL_ID = "mux2"
INPUTS = ('A', 'B', 'S')
TRUTH_TABLE = (0, 0, 0, 1, 1, 0, 1, 1)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
