#!/usr/bin/env python3
"""Auto-generated adapter for buf: Y = A."""

from Database.sdc.sdc_pyscript._comb_cell import configure

CELL_ID = "buf"
INPUTS = ('A',)
TRUTH_TABLE = (0, 1)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
