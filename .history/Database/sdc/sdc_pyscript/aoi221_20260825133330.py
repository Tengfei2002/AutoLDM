#!/usr/bin/env python3
"""Auto-generated adapter for aoi221: Y = !((A & B) | (C & D) | E)."""

from _comb_cell import configure

CELL_ID = "aoi221"
INPUTS = ('A', 'B', 'C', 'D', 'E')
TRUTH_TABLE = (1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
validate, generate_decks, run_and_analyze = configure(CELL_ID, INPUTS, TRUTH_TABLE)
