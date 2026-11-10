#!/usr/bin/env python3
"""Build and validate the AutoLDM 30-cell combinational SDC support library."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import sys
import tempfile
import time
from dataclasses import dataclass
from itertools import combinations, product
from pathlib import Path
from pprint import pformat
from typing import Iterable

sys.dont_write_bytecode = True


ROOT = Path(__file__).resolve().parent
PIN_DIR = ROOT / "sdc_pin"
SCRIPT_DIR = ROOT / "sdc_pyscript"
TB_DIR = ROOT / "sdc_tb"
RUNTIME_TEMPLATE = ROOT / "cell_runtime.py.inc"


@dataclass(frozen=True)
class Cell:
    name: str
    inputs: tuple[str, ...]
    pdn: str
    family: str
    function: str


CELLS = (
    Cell("inv", ("A",), "A", "basic", "Y = !A"),
    Cell("buf", ("A",), "~A", "basic", "Y = A"),
    Cell("nand2", ("A", "B"), "A & B", "basic", "Y = !(A & B)"),
    Cell("nand3", ("A", "B", "C"), "A & B & C", "basic", "Y = !(A & B & C)"),
    Cell("nand4", ("A", "B", "C", "D"), "A & B & C & D", "basic", "Y = !(A & B & C & D)"),
    Cell("nor2", ("A", "B"), "A | B", "basic", "Y = !(A | B)"),
    Cell("nor3", ("A", "B", "C"), "A | B | C", "basic", "Y = !(A | B | C)"),
    Cell("nor4", ("A", "B", "C", "D"), "A | B | C | D", "basic", "Y = !(A | B | C | D)"),
    Cell("and2", ("A", "B"), "~A | ~B", "basic", "Y = A & B"),
    Cell("and3", ("A", "B", "C"), "~A | ~B | ~C", "basic", "Y = A & B & C"),
    Cell("and4", ("A", "B", "C", "D"), "~A | ~B | ~C | ~D", "basic", "Y = A & B & C & D"),
    Cell("or2", ("A", "B"), "~A & ~B", "basic", "Y = A | B"),
    Cell("or3", ("A", "B", "C"), "~A & ~B & ~C", "basic", "Y = A | B | C"),
    Cell("or4", ("A", "B", "C", "D"), "~A & ~B & ~C & ~D", "basic", "Y = A | B | C | D"),
    Cell("aoi21", ("A", "B", "C"), "(A & B) | C", "compound", "Y = !((A & B) | C)"),
    Cell("aoi22", ("A", "B", "C", "D"), "(A & B) | (C & D)", "compound", "Y = !((A & B) | (C & D))"),
    Cell("aoi211", ("A", "B", "C", "D"), "(A & B) | C | D", "compound", "Y = !((A & B) | C | D)"),
    Cell("aoi221", ("A", "B", "C", "D", "E"), "(A & B) | (C & D) | E", "compound", "Y = !((A & B) | (C & D) | E)"),
    Cell("oai21", ("A", "B", "C"), "(A | B) & C", "compound", "Y = !((A | B) & C)"),
    Cell("oai22", ("A", "B", "C", "D"), "(A | B) & (C | D)", "compound", "Y = !((A | B) & (C | D))"),
    Cell("oai211", ("A", "B", "C", "D"), "(A | B) & C & D", "compound", "Y = !((A | B) & C & D)"),
    Cell("oai221", ("A", "B", "C", "D", "E"), "(A | B) & (C | D) & E", "compound", "Y = !((A | B) & (C | D) & E)"),
    Cell("xor2", ("A", "B"), "(A & B) | (~A & ~B)", "arithmetic", "Y = A ^ B"),
    Cell("xnor2", ("A", "B"), "(A & ~B) | (~A & B)", "arithmetic", "Y = !(A ^ B)"),
    Cell("xor3", ("A", "B", "C"), "(~A & ~B & ~C) | (~A & B & C) | (A & ~B & C) | (A & B & ~C)", "arithmetic", "Y = A ^ B ^ C"),
    Cell("xnor3", ("A", "B", "C"), "(~A & ~B & C) | (~A & B & ~C) | (A & ~B & ~C) | (A & B & C)", "arithmetic", "Y = !(A ^ B ^ C)"),
    Cell("mux2", ("A", "B", "S"), "(~S & ~A) | (S & ~B)", "mux", "Y = S ? B : A"),
    Cell("muxi2", ("A", "B", "S"), "(~S & A) | (S & B)", "mux", "Y = !(S ? B : A)"),
    Cell("mux4", ("D0", "D1", "D2", "D3", "S0", "S1"), "(~S1 & ~S0 & ~D0) | (~S1 & S0 & ~D1) | (S1 & ~S0 & ~D2) | (S1 & S0 & ~D3)", "mux", "Y = D[S1:S0]"),
    Cell("maj3", ("A", "B", "C"), "(~A & ~B) | (~A & ~C) | (~B & ~C)", "arithmetic", "Y = majority(A,B,C)"),
)


Node = tuple


def _parse_expression(cell: Cell) -> Node:
    tree = ast.parse(cell.pdn, mode="eval").body

    def visit(node: ast.AST) -> Node:
        if isinstance(node, ast.Name):
            if node.id not in cell.inputs:
                raise ValueError(f"{cell.name}: unknown input {node.id}")
            return ("lit", node.id, False)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert) and isinstance(node.operand, ast.Name):
            if node.operand.id not in cell.inputs:
                raise ValueError(f"{cell.name}: unknown input {node.operand.id}")
            return ("lit", node.operand.id, True)
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitAnd, ast.BitOr)):
            kind = "and" if isinstance(node.op, ast.BitAnd) else "or"
            left, right = visit(node.left), visit(node.right)
            children: list[Node] = []
            for child in (left, right):
                children.extend(child[1]) if child[0] == kind else children.append(child)
            return (kind, tuple(children))
        raise ValueError(f"{cell.name}: only names, ~, &, | and parentheses are supported")

    return visit(tree)


def _literals(node: Node) -> Iterable[tuple[str, bool]]:
    if node[0] == "lit":
        yield node[1], node[2]
    else:
        for child in node[1]:
            yield from _literals(child)


def _eval(node: Node, values: dict[str, bool]) -> bool:
    if node[0] == "lit":
        result = values[node[1]]
        return not result if node[2] else result
    results = [_eval(child, values) for child in node[1]]
    return all(results) if node[0] == "and" else any(results)


def _truth(cell: Cell, node: Node) -> tuple[int, ...]:
    return tuple(
        int(not _eval(node, dict(zip(cell.inputs, vector))))
        for vector in product((False, True), repeat=len(cell.inputs))
    )


class Topology:
    def __init__(self, cell: Cell, expression: Node):
        self.cell = cell
        self.expression = expression
        self.devices: list[dict[str, str]] = []
        self.count = {"N": 0, "P": 0}
        self.net_count = {"N": 0, "P": 0}
        self.complements = tuple(sorted({name for name, inverted in _literals(expression) if inverted}))

    def new_net(self, mos: str) -> str:
        self.net_count[mos] += 1
        return f"{mos}INT{self.net_count[mos]}"

    def add(self, mos: str, start: str, gate: str, end: str) -> None:
        self.count[mos] += 1
        name = f"{mos}{self.count[mos]}"
        source, drain = (end, start) if mos == "N" else (start, end)
        self.devices.append({"name": name, "mos": mos, "s": source, "g": gate,
                             "d": drain, "b": "VSS" if mos == "N" else "VDD"})

    def emit(self, node: Node, start: str, end: str, mos: str, dual: bool) -> None:
        if node[0] == "lit":
            gate = f"{node[1]}N" if node[2] else node[1]
            self.add(mos, start, gate, end)
            return
        series = (node[0] == "and") != dual
        children = node[1]
        if not series:
            for child in children:
                self.emit(child, start, end, mos, dual)
            return
        points = [start, *(self.new_net(mos) for _ in range(len(children) - 1)), end]
        for child, left, right in zip(children, points, points[1:]):
            self.emit(child, left, right, mos, dual)

    def build(self) -> None:
        for input_name in self.complements:
            complement = f"{input_name}N"
            self.add("N", complement, input_name, "VSS")
            self.add("P", "VDD", input_name, complement)
        self.emit(self.expression, "Y", "VSS", "N", False)
        self.emit(self.expression, "VDD", "Y", "P", True)


def _reachable(graph: dict[str, set[str]], start: str) -> set[str]:
    visited: set[str] = set()
    pending = [start]
    while pending:
        node = pending.pop()
        if node in visited:
            continue
        visited.add(node)
        pending.extend(graph.get(node, set()) - visited)
    return visited


def _verify_transistor_network(cell: Cell, topology: Topology, truth: tuple[int, ...]) -> None:
    for vector, expected in zip(product((False, True), repeat=len(cell.inputs)), truth):
        values = dict(zip(cell.inputs, vector))
        values.update({f"{name}N": not values[name] for name in topology.complements})
        graph: dict[str, set[str]] = {}
        for device in topology.devices:
            gate_high = values[device["g"]]
            conducting = gate_high if device["mos"] == "N" else not gate_high
            if conducting:
                graph.setdefault(device["s"], set()).add(device["d"])
                graph.setdefault(device["d"], set()).add(device["s"])
        reached = _reachable(graph, "Y")
        correct_supply = "VDD" if expected else "VSS"
        wrong_supply = "VSS" if expected else "VDD"
        if correct_supply not in reached or wrong_supply in reached:
            bits = "".join("1" if value else "0" for value in vector)
            raise ValueError(
                f"{cell.name}: transistor network mismatch at {bits}; "
                f"expected Y={expected}, reached={sorted(reached)}"
            )


def _unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def _manifest(cell: Cell, topology: Topology) -> str:
    ports = [*cell.inputs, "Y", "VDD", "VSS"]
    logical_nodes = _unique(
        [*ports, *(device[key] for device in topology.devices for key in ("s", "g", "d"))]
    )
    anchors: list[str] = []
    resistor_pairs: list[tuple[str, str]] = []
    fet_rows: list[str] = []
    for device in topology.devices:
        mapped: dict[str, str] = {}
        for terminal in ("s", "g", "d"):
            logical = device[terminal]
            kind = "G" if terminal == "g" else "SD"
            anchor = f"{device['name']}_{kind}_{logical}"
            mapped[terminal] = anchor
            anchors.append(anchor)
            resistor_pairs.append((logical, anchor))
        fet_rows.append(
            f"{device['name']} S={mapped['s']} G={mapped['g']} D={mapped['d']} "
            f"B={device['b']} L=default W=default NF=default"
        )
    r_nodes = _unique([*logical_nodes, *anchors])
    lines = [
        f"(R){{{','.join(r_nodes)}}}",
        *(f"R_{left}_{right}" for left, right in resistor_pairs),
        "",
        f"(C){{{','.join(ports)}}}",
        *(f"C_{left}_{right}" for left, right in combinations(ports, 2)),
        "",
        f"(FET){{{','.join(device['name'] for device in topology.devices)}}}{{S,G,D,B}}",
        *fet_rows,
        "",
        f"(PORT){{{','.join(ports)}}}",
        *(f"{port}={port}" for port in ports),
        "",
    ]
    return "\n".join(lines)


Cube = tuple[int | None, ...]


def _cube_covers(cube: Cube, minterm: tuple[int, ...]) -> bool:
    return all(value is None or value == bit for value, bit in zip(cube, minterm))


def _minimal_cubes(minterms: Iterable[tuple[int, ...]]) -> tuple[Cube, ...]:
    target = set(minterms)
    if not target:
        return ()
    current: set[Cube] = {tuple(item) for item in target}
    primes: set[Cube] = set()
    while current:
        used: set[Cube] = set()
        merged: set[Cube] = set()
        ordered = sorted(current, key=lambda cube: tuple(-1 if value is None else value for value in cube))
        for left_index, left in enumerate(ordered):
            for right in ordered[left_index + 1:]:
                different = [index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]]
                if len(different) != 1:
                    continue
                index = different[0]
                if left[index] is None or right[index] is None:
                    continue
                combined = list(left)
                combined[index] = None
                cube = tuple(combined)
                covered = {item for item in target if _cube_covers(cube, item)}
                expansion_size = 2 ** sum(value is None for value in cube)
                if len(covered) == expansion_size:
                    used.update((left, right))
                    merged.add(cube)
        primes.update(current - used)
        if not merged:
            break
        current = merged

    uncovered = set(target)
    selected: list[Cube] = []
    while uncovered:
        candidates = [
            (len({item for item in uncovered if _cube_covers(cube, item)}),
             sum(value is None for value in cube), cube)
            for cube in primes
        ]
        count, _wildcards, best = max(
            candidates,
            key=lambda item: (item[0], item[1], tuple(-1 if value is None else value for value in item[2])),
        )
        if count == 0:
            raise ValueError("failed to cover timing sensitization minterms")
        selected.append(best)
        uncovered = {item for item in uncovered if not _cube_covers(best, item)}
    return tuple(selected)


def _test_plan(cell: Cell, truth: tuple[int, ...]) -> dict[str, object]:
    if cell.name == "inv":
        strategy = "inverter"
    elif cell.name == "buf":
        strategy = "buffer"
    elif cell.family == "compound":
        strategy = "compound_unate"
    elif cell.family == "mux":
        strategy = "mux"
    elif cell.name.startswith(("xor", "xnor")):
        strategy = "non_unate"
    elif cell.name == "maj3":
        strategy = "threshold"
    else:
        strategy = "static_unate"

    vectors = list(product((0, 1), repeat=len(cell.inputs)))
    truth_by_vector = dict(zip(vectors, truth))
    arcs: list[dict[str, object]] = []
    for input_index, pin in enumerate(cell.inputs):
        other_inputs = tuple(name for index, name in enumerate(cell.inputs) if index != input_index)
        grouped: dict[tuple[int, int], list[tuple[int, ...]]] = {}
        for other_values in product((0, 1), repeat=len(other_inputs)):
            condition = dict(zip(other_inputs, other_values))
            vector0 = tuple(0 if name == pin else condition[name] for name in cell.inputs)
            vector1 = tuple(1 if name == pin else condition[name] for name in cell.inputs)
            y0, y1 = truth_by_vector[vector0], truth_by_vector[vector1]
            if y0 != y1:
                grouped.setdefault((y0, y1), []).append(other_values)
        for (y0, y1), minterms in sorted(grouped.items()):
            for cube_index, cube in enumerate(_minimal_cubes(minterms), 1):
                when = {
                    name: value
                    for name, value in zip(other_inputs, cube)
                    if value is not None
                }
                role = "select" if cell.family == "mux" and pin.startswith("S") else "data" if cell.family == "mux" else "input"
                arcs.append({
                    "name": f"{pin.lower()}_{y0}to{y1}_{cube_index}",
                    "role": role,
                    "pin": pin,
                    "when": when,
                    "y0": y0,
                    "y1": y1,
                })
    dc_sweeps: tuple[dict[str, object], ...] = ()
    if cell.name == "inv":
        dc_sweeps = ({"pin": "A", "when": {}, "y0": 1, "y1": 0},)
    return {
        "strategy": strategy,
        "truth_mode": "exhaustive",
        "static_power_from_truth_decks": True,
        "timing_arcs": tuple(arcs),
        "dc_sweeps": dc_sweeps,
    }


def _adapter(cell: Cell, truth: tuple[int, ...], test_plan: dict[str, object]) -> str:
    plan_text = pformat(test_plan, width=100, sort_dicts=False)
    runtime = RUNTIME_TEMPLATE.read_text(encoding="utf-8").rstrip()
    cell_block = "\n".join([
        "# Cell-specific contract. The runtime above is embedded in this file.",
        "# No other cell Python module is required when this file is loaded.",
        f'CELL_ID = "{cell.name}"',
        f"INPUTS = {cell.inputs!r}",
        f"TRUTH_TABLE = {truth!r}",
        f"TEST_PLAN = {plan_text}",
        "validate, generate_decks, run_and_analyze = configure(",
        "    CELL_ID, INPUTS, TRUTH_TABLE, TEST_PLAN",
        ")",
        "",
    ])
    return runtime + "\n\n" + cell_block


def _bench(cell: Cell) -> str:
    return f"""* AutoLDM benchmark for {cell.name}: {cell.function}
(SUPPLY)
vdd=0.7
vss=0

(LOAD)
cload=5f

(TIMING)
trise=20p
tfall=20p
tdelay=200p
pulse_width=400p
period=1n
tstep=1p
tstop=1.4n
dc_step=1m

(MEASURE)
logic_low_max=0.2
logic_high_min=0.8
"""


def _catalog_and_topologies() -> tuple[list[dict[str, object]], dict[str, Topology]]:
    catalog: list[dict[str, object]] = []
    topologies: dict[str, Topology] = {}
    for cell in CELLS:
        expression = _parse_expression(cell)
        topology = Topology(cell, expression)
        topology.build()
        truth = _truth(cell, expression)
        _verify_transistor_network(cell, topology, truth)
        test_plan = _test_plan(cell, truth)
        topologies[cell.name] = topology
        catalog.append({
            "name": cell.name, "family": cell.family, "inputs": list(cell.inputs),
            "outputs": ["Y"], "ports": [*cell.inputs, "Y", "VDD", "VSS"],
            "function": cell.function, "pdn_expression": cell.pdn,
            "truth_table": list(truth), "complemented_inputs": list(topology.complements),
            "nmos_count": topology.count["N"], "pmos_count": topology.count["P"],
            "transistor_count": len(topology.devices),
            "test_strategy": test_plan["strategy"],
            "timing_arc_count": len(test_plan["timing_arcs"]),
            "dc_sweep_count": len(test_plan["dc_sweeps"]),
        })
    return catalog, topologies


def _readme(catalog: list[dict[str, object]]) -> str:
    rows = [
        "# AutoLDM 组合标准单元支持库",
        "",
        "本目录提供 30 个单输出组合标准单元的 pin manifest、testbench 参数和 HSPICE 适配脚本。",
        "每个单元都由 `build_sdc_library.py` 生成独立 `TEST_PLAN`：包括穷举功能状态、显式时序弧、敏化条件和可选 DC 扫描。",
        "",
        "## 与 TSMC 公开资料的关系",
        "",
        "TSMC 的公开说明确认 Foundation IP 包含 high-density 和 high-performance 标准单元库，",
        "但没有公开原厂完整单元清单、晶体管连接、版图坐标或特征化数据。本目录不是 TSMC 原厂库，",
        "也不包含 TSMC PDK 数据；这里只参考公开说明中的库分类，建立适用于 AutoLDM 的常用逻辑单元集合。",
        "",
        "官方资料：",
        "",
        "- https://pr.tsmc.com/system/files/newspdf/THPGWQTHTH/NEWS_FILE_EN.pdf",
        "- https://pr.tsmc.com/english/news/1224",
        "",
        "## 文件关系",
        "",
        "```text",
        "catalog.json                    机器可读单元目录、真值表和器件数量",
        "sdc_pin/<cell>.txt              R/C/FET/PORT 完整节点约定",
        "sdc_tb/<cell>.txt               供电、负载、时序和判定阈值",
        "sdc_pyscript/<cell>.py          完整独立脚本：单元规则、deck、HSPICE运行和结果分析",
        "cell_runtime.py.inc             仅供生成器嵌入独立脚本，不是运行时依赖",
        "build_sdc_library.py            确定性生成和静态检查入口",
        "```",
        "",
        "## 单元目录",
        "",
        "| 单元 | 类别 | 输入 | 功能 | 测试策略 | 时序弧 | 晶体管数 |",
        "|---|---|---|---|---|---:|---:|",
    ]
    for item in catalog:
        rows.append(f"| `{item['name']}` | {item['family']} | {','.join(item['inputs'])} | `{item['function']}` | `{item['test_strategy']}` | {item['timing_arc_count']} | {item['transistor_count']} |")
    rows.extend([
        "",
        "## 生成和检查",
        "",
        "```powershell",
        "python Database/sdc/build_sdc_library.py",
        "python Database/sdc/build_sdc_library.py --check",
        "python Database/sdc/build_sdc_library.py --cell mux4 --output-root <INPUT_MODEL目录>",
        "python SKILL/autoldm-generate-sdc-cell/scripts/generate_cell.py --cell mux4 --output-root <INPUT_MODEL目录>",
        "```",
        "",
        "最后一条Skill命令还会检查独立导入、接口、deck数量和dry-run结果收集；目标已存在且确认需要替换时增加 `--force`。",
        "选择单元时，`--cell <cell>`、三个同名单元文件和未来对应版图的物理节点标签必须一致。",
        "当前检查能证明目录、逻辑表达式、真值表、manifest、显式时序弧及 deck 生成自洽；只有生成匹配版图和 R/C matrix 后，",
        "才能执行 PEX/HSPICE。这里的内容不代表 foundry signoff、真实 RC 或 TSMC 特征化结果。",
        "",
    ])
    return "\n".join(rows)


def generate_cell(cell_name: str, output_root: Path = ROOT) -> tuple[Path, Path, Path]:
    """Generate one standalone pin/script/testbench triplet by catalog cell name."""
    normalized = cell_name.strip().lower()
    cells = {cell.name: cell for cell in CELLS}
    if normalized not in cells:
        supported = ", ".join(sorted(cells))
        raise ValueError(f"unsupported cell {cell_name!r}; choose one of: {supported}")

    cell = cells[normalized]
    expression = _parse_expression(cell)
    topology = Topology(cell, expression)
    topology.build()
    truth = _truth(cell, expression)
    _verify_transistor_network(cell, topology, truth)

    output_root = Path(output_root).resolve()
    pin_dir = output_root / "sdc_pin"
    script_dir = output_root / "sdc_pyscript"
    tb_dir = output_root / "sdc_tb"
    for directory in (pin_dir, script_dir, tb_dir):
        directory.mkdir(parents=True, exist_ok=True)

    pin_path = pin_dir / f"{cell.name}.txt"
    script_path = script_dir / f"{cell.name}.py"
    tb_path = tb_dir / f"{cell.name}.txt"
    pin_path.write_text(_manifest(cell, topology), encoding="utf-8")
    script_path.write_text(_adapter(cell, truth, _test_plan(cell, truth)), encoding="utf-8")
    tb_path.write_text(_bench(cell), encoding="utf-8")
    return pin_path, script_path, tb_path


def build() -> None:
    for directory in (PIN_DIR, SCRIPT_DIR, TB_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    catalog, topologies = _catalog_and_topologies()
    for cell, item in zip(CELLS, catalog):
        (PIN_DIR / f"{cell.name}.txt").write_text(_manifest(cell, topologies[cell.name]), encoding="utf-8")
        truth = tuple(item["truth_table"])
        (SCRIPT_DIR / f"{cell.name}.py").write_text(
            _adapter(cell, truth, _test_plan(cell, truth)),
            encoding="utf-8",
        )
        (TB_DIR / f"{cell.name}.txt").write_text(_bench(cell), encoding="utf-8")
    (ROOT / "catalog.json").write_text(json.dumps({
        "schema_version": 1,
        "library": "autoldm_combinational_reference",
        "foundry_status": "not_foundry_library",
        "cells": catalog,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (ROOT / "README.md").write_text(_readme(catalog), encoding="utf-8")
    (PIN_DIR / "README.md").write_text(
        "# Pin manifest\n\n每个 `<cell>.txt` 完整定义 `(R)`、`(C)`、`(FET)` 和 `(PORT)`。文件由 `../build_sdc_library.py` 生成。物理节点必须由同名单元版图和 R/C matrix 实现。\n",
        encoding="utf-8",
    )
    (TB_DIR / "README.md").write_text(
        "# Testbench 参数\n\n每个 `<cell>.txt` 定义 0.7 V 供电、输出负载、输入边沿、仿真时间和逻辑阈值；同名单元脚本负责格式检查。\n",
        encoding="utf-8",
    )
    (SCRIPT_DIR / "readme.md").write_text(
        "# 单元适配脚本\n\n每个 `<cell>.py` 都是完整的独立脚本，内含 HSPICE deck 生成、运行、结果解析、`CELL_ID`、`INPUTS`、`TRUTH_TABLE` 和该单元独立的 `TEST_PLAN`。运行时不导入 `_comb_cell.py` 或其他单元脚本。`../cell_runtime.py.inc` 只供生成器构造独立脚本，不能由 FLOW 直接调用。\n",
        encoding="utf-8",
    )


def check() -> None:
    catalog, topologies = _catalog_and_topologies()
    if len(CELLS) != 30 or len({cell.name for cell in CELLS}) != 30:
        raise ValueError("library must contain exactly 30 unique cells")
    on_disk = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8"))
    if on_disk["cells"] != catalog:
        raise ValueError("catalog.json is stale; run the builder")
    sys.path.insert(0, str(SCRIPT_DIR))
    with tempfile.TemporaryDirectory(prefix="autoldm_sdc_check_") as temporary:
      temp_root = Path(temporary)
      n_va = temp_root / "n.va"
      p_va = temp_root / "p.va"
      n_va.write_text("// structural adapter check\n", encoding="utf-8")
      p_va.write_text("// structural adapter check\n", encoding="utf-8")
      for cell, item in zip(CELLS, catalog):
        expected = {
            PIN_DIR / f"{cell.name}.txt",
            SCRIPT_DIR / f"{cell.name}.py",
            TB_DIR / f"{cell.name}.txt",
        }
        missing = [path for path in expected if not path.is_file()]
        if missing:
            raise FileNotFoundError(missing[0])
        pin = (PIN_DIR / f"{cell.name}.txt").read_text(encoding="utf-8")
        for heading in ("(R){", "(C){", "(FET){", "(PORT){"):
            if heading not in pin:
                raise ValueError(f"{cell.name}: missing {heading}")
        fet_header = re.search(r"\(FET\)\{([^}]*)\}\{S,G,D,B\}", pin)
        port_header = re.search(r"\(PORT\)\{([^}]*)\}", pin)
        if not fet_header or len(fet_header.group(1).split(",")) != item["transistor_count"]:
            raise ValueError(f"{cell.name}: FET count mismatch")
        if not port_header or port_header.group(1).split(",") != item["ports"]:
            raise ValueError(f"{cell.name}: port order mismatch")
        path = SCRIPT_DIR / f"{cell.name}.py"
        spec = importlib.util.spec_from_file_location(f"sdc_check_{cell.name}", path)
        if spec is None or spec.loader is None:
            raise ImportError(path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        for attempt in range(3):
            try:
                spec.loader.exec_module(module)
                break
            except PermissionError:
                if attempt == 2:
                    raise
                time.sleep(0.1)
        if module.CELL_ID != cell.name or tuple(module.INPUTS) != cell.inputs:
            raise ValueError(f"{cell.name}: adapter identity mismatch")
        if tuple(module.TRUTH_TABLE) != tuple(item["truth_table"]):
            raise ValueError(f"{cell.name}: adapter truth table mismatch")
        expected_plan = _test_plan(cell, tuple(item["truth_table"]))
        if module.TEST_PLAN != expected_plan:
            raise ValueError(f"{cell.name}: adapter test plan mismatch")
        if _manifest(cell, topologies[cell.name]) != pin:
            raise ValueError(f"{cell.name}: pin manifest is stale")
        inc = temp_root / f"{cell.name}.inc"
        inc.write_text(
            f".subckt {cell.name}_check {' '.join(item['ports'])}\n.ends {cell.name}_check\n",
            encoding="utf-8",
        )
        bench = TB_DIR / f"{cell.name}.txt"
        module.validate(inc, bench, n_va, p_va)
        decks = module.generate_decks(inc, bench, n_va, p_va, temp_root / cell.name)
        expected_decks = (
            2 ** len(cell.inputs)
            + len(expected_plan["timing_arcs"])
            + len(expected_plan["dc_sweeps"])
        )
        if len(decks) != expected_decks or not all(deck.is_file() for deck in decks):
            raise ValueError(f"{cell.name}: expected {expected_decks} generated decks")
        if module.run_and_analyze(
            temp_root / cell.name,
            temp_root / f"{cell.name}_results",
            dry_run=True,
            no_plot=True,
        ):
            raise ValueError(f"{cell.name}: dry-run result collection failed")
    print(f"PASS: {len(CELLS)} cells; catalog, adapters, truth tables and manifests are consistent")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate existing generated files without rewriting")
    parser.add_argument("--cell", help="generate only one catalog cell")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT,
        help="root containing sdc_pin, sdc_pyscript and sdc_tb",
    )
    args = parser.parse_args()
    if args.check and args.cell:
        parser.error("--check and --cell cannot be used together")
    if args.cell:
        paths = generate_cell(args.cell, args.output_root)
        print("Generated standalone triplet:")
        for path in paths:
            print(path)
        return 0
    if not args.check:
        build()
        print(f"Generated {len(CELLS)} standard-cell triplets under {ROOT}")
    check()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
