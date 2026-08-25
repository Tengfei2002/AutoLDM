#!/usr/bin/env python3
"""Auto-generated adapter for oai21: Y = !((A | B) & C)."""

from Database.sdc.sdc_pyscript._comb_cell import configure

CELL_ID = "oai21"
INPUTS = ('A', 'B', 'C')
TRUTH_TABLE = (1, 1, 1, 0, 1, 0, 1, 0)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
