#!/usr/bin/env python3
"""Generate pin-level RC, a reusable PEX include, and its validation deck."""

from __future__ import annotations

import argparse
import re
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path
from typing import Iterable


MATRIX_RE = re.compile(r"^\s*([RC])_\S+\s+(\S+)\s+(\S+)\s+(\S+)\s*$", re.IGNORECASE)
HEADER_RE = re.compile(r"^\s*\(([RC])\)\s*\{([^}]*)\}\s*$", re.IGNORECASE)
AUXILIARY_HEADER_RE = re.compile(r"^\s*\((?:FET|PORT)\)\s*\{", re.IGNORECASE)
CONTACT_FACE_RE = re.compile(
    r"^Contact_(?P<layer>[^_]+)(?:_.*)?_(?P<face>Top|Bottom)$",
    re.IGNORECASE,
)
COMMENT_PREFIXES = ("*", "#", "%", ";")
NETWORK_DECIMAL_PRECISION = 80

MatrixEntry = tuple[str, str, str, Decimal]


@dataclass(frozen=True)
class RequestedPair:
    element_name: str
    first: str
    second: str


@dataclass(frozen=True)
class PinManifest:
    r_pins: tuple[str, ...]
    r_pairs: tuple[RequestedPair, ...]
    c_pins: tuple[str, ...]
    c_pairs: tuple[RequestedPair, ...]
    auxiliary_lines: tuple[str, ...]


@dataclass(frozen=True)
class ContactFacePolicy:
    """Technology naming policy for selecting one face of each contact body."""

    md_layer: str = "MD"
    bmd_layer: str = "BMD"
    backside_prefix: str = "B"
    strict: bool = False

    def preferred_face(self, layer: str) -> str:
        normalized = layer.upper()
        if normalized == self.md_layer.upper():
            return "Bottom"
        if normalized == self.bmd_layer.upper():
            return "Top"
        if normalized.startswith(self.backside_prefix.upper()):
            return "Bottom"
        return "Top"


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, first: str, second: str) -> None:
        first_root, second_root = self.find(first), self.find(second)
        if first_root != second_root:
            self.parent[second_root] = first_root


@dataclass
class ResistanceNetwork:
    """A passive resistor network built from all Raphael R-matrix branches."""

    contact_node: dict[str, str]
    adjacency: dict[str, dict[str, Decimal]]

    @classmethod
    def from_entries(cls, entries: Iterable[MatrixEntry]) -> "ResistanceNetwork":
        """Contract ideal shorts and accumulate all finite branches as conductance."""
        uf = UnionFind()
        nodes: set[str] = set()
        finite_edges: list[tuple[str, str, Decimal]] = []

        for kind, first, second, value in entries:
            if kind != "R":
                continue
            nodes.update((first, second))
            uf.find(first)
            uf.find(second)
            if value.is_nan() or (value.is_signed() and not value.is_zero()):
                raise ValueError(
                    f"Invalid resistance between {first!r} and {second!r}: {value}"
                )
            if value.is_zero():
                uf.union(first, second)
            elif value.is_finite():
                finite_edges.append((first, second, value))

        if not nodes:
            raise ValueError("R matrix contains no resistance endpoints")

        contact_node = {contact: uf.find(contact) for contact in nodes}
        adjacency: dict[str, dict[str, Decimal]] = {
            node: {} for node in set(contact_node.values())
        }
        with localcontext() as context:
            context.prec = NETWORK_DECIMAL_PRECISION
            for first, second, resistance in finite_edges:
                first_node = contact_node[first]
                second_node = contact_node[second]
                if first_node == second_node:
                    continue
                conductance = Decimal(1) / resistance
                adjacency[first_node][second_node] = (
                    adjacency[first_node].get(second_node, Decimal(0)) + conductance
                )
                adjacency[second_node][first_node] = (
                    adjacency[second_node].get(first_node, Decimal(0)) + conductance
                )
        return cls(contact_node, adjacency)

    def _terminal_nodes(self, contacts: Iterable[str]) -> set[str]:
        missing = sorted(set(contacts) - self.contact_node.keys())
        if missing:
            raise ValueError(
                "R-network contact(s) are absent from the matrix: " + ", ".join(missing)
            )
        return {self.contact_node[contact] for contact in contacts}

    def _connected_components(self) -> list[set[str]]:
        remaining = set(self.adjacency)
        components: list[set[str]] = []
        while remaining:
            seed = remaining.pop()
            component = {seed}
            pending = [seed]
            while pending:
                node = pending.pop()
                for neighbor in self.adjacency[node]:
                    if neighbor not in component:
                        component.add(neighbor)
                        remaining.discard(neighbor)
                        pending.append(neighbor)
            components.append(component)
        return components

    @staticmethod
    def _solve_linear_system(
        matrix: list[list[Decimal]], rhs: list[Decimal]
    ) -> list[Decimal]:
        """Solve a dense Decimal system with partial-pivot Gaussian elimination."""
        size = len(rhs)
        if size == 0:
            return []
        a = [row[:] + [rhs_value] for row, rhs_value in zip(matrix, rhs)]
        for column in range(size):
            pivot_row = max(range(column, size), key=lambda row: abs(a[row][column]))
            if a[pivot_row][column].is_zero():
                raise ValueError("Singular grounded conductance matrix")
            if pivot_row != column:
                a[column], a[pivot_row] = a[pivot_row], a[column]
            pivot = a[column][column]
            for row in range(column + 1, size):
                if a[row][column].is_zero():
                    continue
                factor = a[row][column] / pivot
                a[row][column] = Decimal(0)
                for index in range(column + 1, size + 1):
                    a[row][index] -= factor * a[column][index]

        solution = [Decimal(0)] * size
        for row in range(size - 1, -1, -1):
            residual = a[row][size] - sum(
                (a[row][column] * solution[column] for column in range(row + 1, size)),
                Decimal(0),
            )
            solution[row] = residual / a[row][row]
        return solution

    def _component_conductance(
        self,
        component: set[str],
        source_nodes: set[str],
        sink_nodes: set[str],
    ) -> Decimal:
        """Solve one connected component with source=1 V and sink=0 V."""
        sources = component & source_nodes
        sinks = component & sink_nodes
        internal = sorted(component - sources - sinks)
        internal_index = {node: index for index, node in enumerate(internal)}
        size = len(internal)
        matrix = [[Decimal(0) for _ in range(size)] for _ in range(size)]
        rhs = [Decimal(0) for _ in range(size)]

        for node, row in internal_index.items():
            for neighbor, conductance in self.adjacency[node].items():
                matrix[row][row] += conductance
                if neighbor in internal_index:
                    matrix[row][internal_index[neighbor]] -= conductance
                elif neighbor in sources:
                    rhs[row] += conductance

        voltages = {
            **{node: Decimal(1) for node in sources},
            **{node: Decimal(0) for node in sinks},
            **dict(zip(internal, self._solve_linear_system(matrix, rhs))),
        }
        current = Decimal(0)
        for source in sources:
            for neighbor, conductance in self.adjacency[source].items():
                if neighbor not in sources:
                    current += conductance * (Decimal(1) - voltages[neighbor])
        return current

    def equivalent_resistance(
        self, source_contacts: Iterable[str], sink_contacts: Iterable[str]
    ) -> Decimal:
        """Return two-terminal resistance with each contact group shorted externally."""
        source_nodes = self._terminal_nodes(source_contacts)
        sink_nodes = self._terminal_nodes(sink_contacts)
        if source_nodes & sink_nodes:
            return Decimal(0)

        with localcontext() as context:
            context.prec = NETWORK_DECIMAL_PRECISION
            total_conductance = Decimal(0)
            for component in self._connected_components():
                if component & source_nodes and component & sink_nodes:
                    total_conductance += self._component_conductance(
                        component, source_nodes, sink_nodes
                    )
            if total_conductance <= 0:
                return Decimal("Infinity")
            return Decimal(1) / total_conductance


def read_matrix(path: Path) -> list[MatrixEntry]:
    """Read R/C entries from a DVS matrix SPICE file."""
    entries: list[MatrixEntry] = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        match = MATRIX_RE.match(line)
        if not match:
            continue
        kind, first, second, raw_value = match.groups()
        try:
            value = Decimal(raw_value)
        except InvalidOperation as exc:
            raise ValueError(f"{path}:{number}: invalid matrix value {raw_value!r}") from exc
        entries.append((kind.upper(), first, second, value))
    if not entries:
        raise ValueError(f"No R/C matrix entries found in {path}")
    return entries


def parse_header_names(path: Path, number: int, raw_names: str) -> tuple[str, ...]:
    names = tuple(name.strip() for name in raw_names.split(",") if name.strip())
    if not names:
        raise ValueError(f"{path}:{number}: empty pin declaration")
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"{path}:{number}: duplicate declared names: {', '.join(duplicates)}")
    return names


def resolve_requested_pair(path: Path, number: int, line: str, pins: tuple[str, ...]) -> RequestedPair:
    """Resolve an underscore-containing element name against declared pins."""
    kind = line[0].upper()
    body = line[2:]
    matches = [
        (first, second)
        for first in pins
        for second in pins
        if first != second and body == f"{first}_{second}"
    ]
    if len(matches) != 1:
        detail = "no declared pin pair" if not matches else f"ambiguous pairs: {matches}"
        raise ValueError(f"{path}:{number}: cannot resolve {line!r}: {detail}")
    first, second = matches[0]
    return RequestedPair(f"{kind}_{body}", first, second)


def read_pin_manifest(path: Path) -> PinManifest:
    """Read R/C declarations and preserve trailing FET/PORT topology text."""
    headers: dict[str, tuple[str, ...]] = {}
    pending: list[tuple[int, str, str]] = []
    auxiliary_lines: list[str] = []
    reading_auxiliary = False

    for number, raw_line in enumerate(path.read_text(encoding="utf-8-sig", errors="replace").splitlines(), 1):
        line = raw_line.strip()
        if AUXILIARY_HEADER_RE.match(line):
            reading_auxiliary = True
            auxiliary_lines.append(raw_line)
            continue
        if reading_auxiliary:
            auxiliary_lines.append(raw_line)
            continue
        if not line or line.startswith(COMMENT_PREFIXES):
            continue
        header = HEADER_RE.match(line)
        if header:
            kind, raw_names = header.groups()
            kind = kind.upper()
            if kind in headers:
                raise ValueError(f"{path}:{number}: duplicate ({kind}) header")
            headers[kind] = parse_header_names(path, number, raw_names)
            continue
        if len(line) > 2 and line[0].upper() in {"R", "C"} and line[1] == "_":
            pending.append((number, line[0].upper(), line))
            continue
        raise ValueError(f"{path}:{number}: unsupported pin-manifest line: {line!r}")

    for kind in ("R", "C"):
        if kind not in headers:
            raise ValueError(f"{path}: missing ({kind}){{...}} declaration")

    resolved: dict[str, list[RequestedPair]] = {"R": [], "C": []}
    seen_elements: set[str] = set()
    for number, kind, line in pending:
        pair = resolve_requested_pair(path, number, line, headers[kind])
        if pair.element_name in seen_elements:
            raise ValueError(f"{path}:{number}: duplicate requested element {pair.element_name}")
        seen_elements.add(pair.element_name)
        resolved[kind].append(pair)

    return PinManifest(
        r_pins=headers["R"],
        r_pairs=tuple(resolved["R"]),
        c_pins=headers["C"],
        c_pairs=tuple(resolved["C"]),
        auxiliary_lines=tuple(auxiliary_lines),
    )


def name_occurs_in_endpoint(endpoint: str, declared_name: str) -> bool:
    """Match a declared name as underscore/punctuation-delimited tokens."""
    pattern = rf"(?<![A-Za-z0-9]){re.escape(declared_name)}(?![A-Za-z0-9])"
    return re.search(pattern, endpoint) is not None


def maximal_declared_matches(endpoint: str, declared_names: Iterable[str]) -> tuple[str, ...]:
    """Return the most specific declared names occurring in an endpoint.

    For example, when both ``NET`` and ``DEVICE_NET`` are declared, a contact
    containing ``DEVICE_NET`` maps to the longer name only. A combined contact
    containing two unrelated long names maps to both of them.
    """
    matches = [name for name in declared_names if name_occurs_in_endpoint(endpoint, name)]
    return tuple(
        name
        for name in matches
        if not any(
            name != other and name_occurs_in_endpoint(other, name)
            for other in matches
        )
    )


def matrix_endpoints(entries: Iterable[MatrixEntry]) -> set[str]:
    return {node for _kind, first, second, _value in entries for node in (first, second)}


def select_preferred_contact_faces(
    endpoints: Iterable[str],
    policy: ContactFacePolicy,
    fallback_notes: set[str] | None = None,
) -> list[str]:
    """Select the technology-preferred face for every matched contact body.

    Selection is performed per contact body. If the preferred face is absent,
    the available face is retained so incomplete matrix exports remain usable.
    Endpoints without a recognizable ``Contact_<layer>_..._<face>`` structure
    are also retained.
    """
    by_body: dict[str, list[str]] = defaultdict(list)
    for endpoint in endpoints:
        body, separator, _face = endpoint.rpartition("_")
        by_body[body if separator else endpoint].append(endpoint)

    selected: list[str] = []
    for group in by_body.values():
        parsed = [(endpoint, CONTACT_FACE_RE.match(endpoint)) for endpoint in group]
        recognized = [(endpoint, match) for endpoint, match in parsed if match]
        if not recognized:
            selected.extend(group)
            continue
        layer = recognized[0][1].group("layer")
        preferred = policy.preferred_face(layer)
        preferred_endpoints = [
            endpoint
            for endpoint, match in recognized
            if match.group("face").casefold() == preferred.casefold()
        ]
        if preferred_endpoints:
            selected.extend(preferred_endpoints)
            continue
        body = group[0].rsplit("_", 1)[0]
        message = (
            f"{body}: preferred {preferred} face for layer {layer} is absent; "
            "using available face(s)"
        )
        if policy.strict:
            raise ValueError(message)
        if fallback_notes is not None:
            fallback_notes.add(message)
        selected.extend(group)
    return sorted(set(selected))


def candidates_by_pin(
    entries: Iterable[MatrixEntry],
    declared_pins: tuple[str, ...],
    policy: ContactFacePolicy,
) -> tuple[dict[str, list[str]], set[str]]:
    """Map manifest-declared R pins to DVS contact names without naming rules."""
    candidates: dict[str, list[str]] = {pin: [] for pin in declared_pins}
    fallback_notes: set[str] = set()
    for endpoint in sorted(matrix_endpoints(entries)):
        for pin in maximal_declared_matches(endpoint, declared_pins):
            candidates[pin].append(endpoint)
    for pin in candidates:
        candidates[pin] = select_preferred_contact_faces(
            candidates[pin], policy, fallback_notes
        )
    return candidates, fallback_notes


def c_node_pin_map(entries: Iterable[MatrixEntry], declared_pins: tuple[str, ...]) -> dict[str, str]:
    """Map zero-ohm-contracted C body nodes to names declared in (C){...}."""
    uf = UnionFind()
    nodes: set[str] = set()
    for kind, first, second, value in entries:
        nodes.update((first, second))
        uf.find(first)
        uf.find(second)
        if kind == "R" and value == 0:
            uf.union(first, second)

    components: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        components[uf.find(node)].add(node)

    node_to_pin: dict[str, str] = {}
    for members in components.values():
        matched_pins = {
            pin
            for member in members
            for pin in maximal_declared_matches(member, declared_pins)
        }
        if len(matched_pins) > 1:
            raise ValueError(
                "A zero-ohm C component matches multiple declared pins "
                f"{sorted(matched_pins)}: {', '.join(sorted(members))}"
            )
        if matched_pins:
            pin = next(iter(matched_pins))
            node_to_pin.update({member: pin for member in members})

    missing = [pin for pin in declared_pins if pin not in node_to_pin.values()]
    if missing:
        raise ValueError(
            "No C-matrix node/component matches declared (C) pins: " + ", ".join(missing)
        )
    return node_to_pin


def merged_capacitances(
    entries: Iterable[MatrixEntry], node_to_pin: dict[str, str]
) -> dict[frozenset[str], Decimal]:
    """Sum C branches between manifest-declared logical pins."""
    merged: dict[frozenset[str], Decimal] = defaultdict(Decimal)
    for kind, first, second, value in entries:
        if kind != "C" or first not in node_to_pin or second not in node_to_pin:
            continue
        first_pin, second_pin = node_to_pin[first], node_to_pin[second]
        if first_pin != second_pin:
            merged[frozenset((first_pin, second_pin))] += value
    return dict(merged)


def requested_resistance(
    pair: RequestedPair,
    candidates: dict[str, list[str]],
    network: ResistanceNetwork,
) -> tuple[Decimal, tuple[str, ...], tuple[str, ...]]:
    """Solve one requested pin pair using all branches in the R network."""
    first_candidates = candidates.get(pair.first, [])
    second_candidates = candidates.get(pair.second, [])
    if not first_candidates or not second_candidates:
        raise ValueError(
            f"{pair.element_name}: no R-matrix contact matches "
            f"{pair.first!r} or {pair.second!r}; candidates are "
            f"{first_candidates} / {second_candidates}"
        )

    first_contacts = tuple(sorted(set(first_candidates)))
    second_contacts = tuple(sorted(set(second_candidates)))
    value = network.equivalent_resistance(first_contacts, second_contacts)
    return value, first_contacts, second_contacts


def spice_number(value: Decimal) -> str:
    if not value.is_finite():
        return "1.00000000e+99"
    if value.is_zero():
        return "0.00000000e+00"
    return format(value, ".8E").replace("E", "e")


def render_spice(
    _manifest_path: Path,
    manifest: PinManifest,
    c_entries: list[MatrixEntry],
    r_entries: list[MatrixEntry],
    face_policy: ContactFacePolicy,
) -> str:
    r_candidates, _face_fallbacks = candidates_by_pin(
        r_entries, manifest.r_pins, face_policy
    )
    r_network = ResistanceNetwork.from_entries(r_entries)
    c_nodes = c_node_pin_map(c_entries, manifest.c_pins)
    c_values = merged_capacitances(c_entries, c_nodes)

    lines = [f"(R){{{','.join(manifest.r_pins)}}}"]
    for pair in manifest.r_pairs:
        value, _first_contacts, _second_contacts = requested_resistance(
            pair, r_candidates, r_network
        )
        lines.append(
            f"{pair.element_name} {pair.first} {pair.second} {spice_number(value)}"
        )

    lines.extend(("", f"(C){{{','.join(manifest.c_pins)}}}"))
    for pair in manifest.c_pairs:
        value = c_values.get(frozenset((pair.first, pair.second)), Decimal(0))
        lines.append(
            f"{pair.element_name} {pair.first} {pair.second} {spice_number(value)}"
        )
    output = "\n".join(lines) + "\n"
    if manifest.auxiliary_lines:
        output += "\n" + "\n".join(manifest.auxiliary_lines) + "\n"
    return output

import argparse
import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path


RC_HEADER_RE = re.compile(r"^\s*\(([RC])\)\s*\{([^}]*)\}\s*$", re.IGNORECASE)
FET_HEADER_RE = re.compile(
    r"^\s*\(FET\)\s*\{([^}]*)\}\s*\{([^}]*)\}\s*$", re.IGNORECASE
)
PORT_HEADER_RE = re.compile(r"^\s*\(PORT\)\s*\{([^}]*)\}\s*$", re.IGNORECASE)
RC_ELEMENT_RE = re.compile(
    r"^\s*([RC]\S*)\s+(\S+)\s+(\S+)\s+(\S+)(?:\s+\$.*)?$",
    re.IGNORECASE,
)
MODULE_RE = re.compile(
    r"\bmodule\s+([A-Za-z_][A-Za-z0-9_$]*)\s*\(([^)]*)\)\s*;",
    re.IGNORECASE | re.MULTILINE,
)
PARAMETER_RE = re.compile(
    r"\bparameter\s+(?:real|integer)\s+([A-Za-z_][A-Za-z0-9_$]*)"
    r"\s*=\s*([^;]+);",
    re.IGNORECASE,
)
SAFE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.$]*$")
COMMENT_PREFIXES = ("*", "#", "%", ";")


@dataclass(frozen=True)
class RCElement:
    name: str
    first: str
    second: str
    value: Decimal
    raw_value: str


@dataclass(frozen=True)
class VAModule:
    path: Path
    name: str
    ports: tuple[str, ...]
    parameter_defaults: dict[str, str]


@dataclass(frozen=True)
class FETInstance:
    name: str
    model_kind: str
    terminals: dict[str, str]
    parameters: dict[str, str]


@dataclass(frozen=True)
class CircuitInput:
    declared_rc_nodes: dict[str, tuple[str, ...]]
    resistors: tuple[RCElement, ...]
    capacitors: tuple[RCElement, ...]
    terminal_names: tuple[str, ...]
    instances: tuple[FETInstance, ...]
    ports: tuple[str, ...]
    port_anchors: dict[str, str]


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        if self.parent[item] != item:
            self.parent[item] = self.find(self.parent[item])
        return self.parent[item]

    def union(self, first: str, second: str) -> None:
        first_root = self.find(first)
        second_root = self.find(second)
        if first_root != second_root:
            self.parent[second_root] = first_root


def split_names(path: Path, number: int, raw_names: str, label: str) -> tuple[str, ...]:
    names = tuple(item.strip() for item in raw_names.split(",") if item.strip())
    if not names:
        raise ValueError(f"{path}:{number}: empty {label} declaration")
    if len(names) != len(set(names)):
        raise ValueError(f"{path}:{number}: duplicate name in {label} declaration")
    for name in names:
        ensure_name(path, number, label, name)
    return names


def ensure_name(path: Path, number: int, kind: str, name: str) -> None:
    if not SAFE_NAME_RE.fullmatch(name):
        raise ValueError(f"{path}:{number}: invalid {kind} name {name!r}")


def parse_number(path: Path, number: int, raw_value: str) -> Decimal:
    try:
        value = Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValueError(f"{path}:{number}: invalid passive value {raw_value!r}") from exc
    if not value.is_finite() or (value.is_signed() and not value.is_zero()):
        raise ValueError(f"{path}:{number}: passive value must be finite and nonnegative")
    return value


def parse_assignments(
    path: Path, number: int, fields: list[str]
) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for field in fields:
        key, separator, value = field.partition("=")
        key = key.strip().upper()
        value = value.strip()
        if not separator or not key or not value:
            raise ValueError(f"{path}:{number}: invalid assignment {field!r}")
        ensure_name(path, number, "assignment", key)
        if key in assignments:
            raise ValueError(f"{path}:{number}: duplicate assignment {key}")
        assignments[key] = value
    return assignments


def read_va_module(path: Path) -> VAModule:
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    matches = MODULE_RE.findall(source)
    if len(matches) != 1:
        raise ValueError(
            f"{path}: expected exactly one Verilog-A module, found {len(matches)}"
        )
    module_name, raw_ports = matches[0]
    ports = tuple(item.strip().upper() for item in raw_ports.split(",") if item.strip())
    if not ports or len(ports) != len(set(ports)):
        raise ValueError(f"{path}: module {module_name} has invalid or duplicate ports")
    ensure_name(path, 0, "module", module_name)
    for port in ports:
        ensure_name(path, 0, "module port", port)
    parameter_defaults = {
        name.upper(): value.strip()
        for name, value in PARAMETER_RE.findall(source)
    }
    return VAModule(path.resolve(), module_name, ports, parameter_defaults)


def read_circuit_input(
    path: Path, modules: dict[str, VAModule]
) -> CircuitInput:
    declared_rc_nodes: dict[str, tuple[str, ...]] = {}
    elements: dict[str, list[RCElement]] = {"R": [], "C": []}
    element_names: set[str] = set()
    declared_instances: tuple[str, ...] | None = None
    terminal_names: tuple[str, ...] | None = None
    instances: list[FETInstance] = []
    ports: tuple[str, ...] | None = None
    port_anchors: dict[str, str] = {}
    section: str | None = None

    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    for number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith(COMMENT_PREFIXES):
            continue

        rc_header = RC_HEADER_RE.match(line)
        if rc_header:
            kind, raw_names = rc_header.groups()
            kind = kind.upper()
            if kind in declared_rc_nodes:
                raise ValueError(f"{path}:{number}: duplicate ({kind}) section")
            declared_rc_nodes[kind] = split_names(
                path, number, raw_names, f"({kind}) node"
            )
            section = kind
            continue

        fet_header = FET_HEADER_RE.match(line)
        if fet_header:
            if declared_instances is not None:
                raise ValueError(f"{path}:{number}: duplicate (FET) section")
            declared_instances = split_names(
                path, number, fet_header.group(1), "(FET) instance"
            )
            terminal_names = tuple(
                item.upper()
                for item in split_names(
                    path, number, fet_header.group(2), "(FET) terminal"
                )
            )
            expected_port_sets = {module.ports for module in modules.values()}
            if len(expected_port_sets) != 1:
                raise ValueError(
                    "NMOS and PMOS Verilog-A modules must expose the same ports"
                )
            expected_ports = next(iter(expected_port_sets))
            if set(terminal_names) != set(expected_ports):
                raise ValueError(
                    f"{path}:{number}: FET terminals {terminal_names} do not match "
                    f"Verilog-A ports {expected_ports}"
                )
            section = "FET"
            continue

        port_header = PORT_HEADER_RE.match(line)
        if port_header:
            if ports is not None:
                raise ValueError(f"{path}:{number}: duplicate (PORT) section")
            ports = split_names(path, number, port_header.group(1), "(PORT)")
            section = "PORT"
            continue

        if section in {"R", "C"}:
            match = RC_ELEMENT_RE.match(line)
            if not match:
                raise ValueError(f"{path}:{number}: invalid {section} element line")
            name, first, second, raw_value = match.groups()
            kind = name[0].upper()
            if kind != section:
                raise ValueError(
                    f"{path}:{number}: {name} appears inside ({section}) section"
                )
            if name in element_names:
                raise ValueError(f"{path}:{number}: duplicate element {name}")
            for node in (first, second):
                ensure_name(path, number, "node", node)
            element_names.add(name)
            elements[kind].append(
                RCElement(
                    name,
                    first,
                    second,
                    parse_number(path, number, raw_value),
                    raw_value,
                )
            )
            continue

        if section == "FET":
            fields = line.split()
            instance_name = fields[0]
            if declared_instances is None or instance_name not in declared_instances:
                raise ValueError(
                    f"{path}:{number}: undeclared FET instance {instance_name!r}"
                )
            if any(item.name == instance_name for item in instances):
                raise ValueError(
                    f"{path}:{number}: duplicate FET instance {instance_name}"
                )
            model_kind = instance_name[0].upper()
            if model_kind not in modules:
                raise ValueError(
                    f"{path}:{number}: FET instance {instance_name!r} must begin "
                    f"with one of {', '.join(sorted(modules))}"
                )
            assignments = parse_assignments(path, number, fields[1:])
            assert terminal_names is not None
            missing_terminals = sorted(set(terminal_names) - assignments.keys())
            if missing_terminals:
                raise ValueError(
                    f"{path}:{number}: {instance_name} lacks terminal assignments "
                    + ", ".join(missing_terminals)
                )
            terminals = {name: assignments.pop(name) for name in terminal_names}
            for node in terminals.values():
                ensure_name(path, number, "terminal node", node)
            parameters = dict(assignments)
            instances.append(
                FETInstance(instance_name, model_kind, terminals, parameters)
            )
            continue

        if section == "PORT":
            port, separator, physical_node = line.partition("=")
            port = port.strip()
            physical_node = physical_node.strip()
            if not separator or not port or not physical_node:
                raise ValueError(
                    f"{path}:{number}: PORT mapping must be PORT=PHYSICAL_NODE"
                )
            if ports is None or port not in ports:
                raise ValueError(f"{path}:{number}: undeclared port {port!r}")
            if port in port_anchors:
                raise ValueError(f"{path}:{number}: duplicate mapping for port {port}")
            ensure_name(path, number, "physical node", physical_node)
            port_anchors[port] = physical_node
            continue

        raise ValueError(f"{path}:{number}: data appears before a section header")

    for kind in ("R", "C"):
        if kind not in declared_rc_nodes:
            raise ValueError(f"{path}: missing ({kind}) section")
    if declared_instances is None or terminal_names is None:
        raise ValueError(f"{path}: missing (FET) section")
    if ports is None:
        raise ValueError(f"{path}: missing (PORT) section")
    actual_instances = {item.name for item in instances}
    if actual_instances != set(declared_instances):
        missing = sorted(set(declared_instances) - actual_instances)
        extra = sorted(actual_instances - set(declared_instances))
        raise ValueError(
            f"{path}: FET declaration mismatch; missing={missing}, extra={extra}"
        )
    if set(port_anchors) != set(ports):
        missing = sorted(set(ports) - set(port_anchors))
        raise ValueError(f"{path}: missing PORT mappings: {', '.join(missing)}")

    return CircuitInput(
        declared_rc_nodes,
        tuple(elements["R"]),
        tuple(elements["C"]),
        terminal_names,
        tuple(instances),
        ports,
        port_anchors,
    )


def canonical_node_map(circuit: CircuitInput) -> dict[str, str]:
    union_find = UnionFind()
    nodes: set[str] = set(circuit.ports)
    nodes.update(circuit.port_anchors.values())
    for element in (*circuit.resistors, *circuit.capacitors):
        nodes.update((element.first, element.second))
    for instance in circuit.instances:
        nodes.update(instance.terminals.values())
    for node in nodes:
        union_find.find(node)
    for resistor in circuit.resistors:
        if resistor.value.is_zero():
            union_find.union(resistor.first, resistor.second)
    for port, physical_node in circuit.port_anchors.items():
        union_find.union(port, physical_node)

    components: dict[str, set[str]] = {}
    for node in nodes:
        components.setdefault(union_find.find(node), set()).add(node)

    canonical_by_root: dict[str, str] = {}
    port_set = set(circuit.ports)
    for root, members in components.items():
        component_ports = [port for port in circuit.ports if port in members]
        if len(component_ports) > 1:
            raise ValueError(
                "PORT mappings or zero-ohm resistors short external ports: "
                + ", ".join(component_ports)
            )
        canonical_by_root[root] = (
            component_ports[0] if component_ports else sorted(members)[0]
        )
    return {
        node: canonical_by_root[union_find.find(node)]
        for node in nodes
    }


def relative_path(target: Path, owner: Path) -> str:
    return os.path.relpath(target.resolve(), owner.parent.resolve()).replace("\\", "/")


def normalized_subcircuit_name(raw_name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.$]", "_", raw_name)
    if not name:
        name = "AUTOLDM_CELL"
    if name[0].isdigit():
        name = f"CELL_{name}"
    if not SAFE_NAME_RE.fullmatch(name):
        raise ValueError(f"Cannot derive a valid subcircuit name from {raw_name!r}")
    return name.upper()


def render_library(
    subcircuit_name: str,
    circuit: CircuitInput,
    modules: dict[str, VAModule],
    node_map: dict[str, str],
) -> str:
    lines = [
        "* AutoLDM data-driven extracted-RC subcircuit library",
        f".subckt {subcircuit_name} {' '.join(circuit.ports)}",
    ]
    aliases = sorted(
        (source, target)
        for source, target in node_map.items()
        if source != target
    )
    if aliases:
        lines.append("* Canonical aliases from PORT mappings and zero-ohm R:")
        lines.extend(f"*   {source} -> {target}" for source, target in aliases)

    for resistor in circuit.resistors:
        if resistor.value.is_zero():
            continue
        first = node_map[resistor.first]
        second = node_map[resistor.second]
        if first != second:
            lines.append(
                f"{resistor.name} {first} {second} {resistor.raw_value}"
            )
    for capacitor in circuit.capacitors:
        if capacitor.value.is_zero():
            continue
        first = node_map[capacitor.first]
        second = node_map[capacitor.second]
        if first != second:
            lines.append(
                f"{capacitor.name} {first} {second} {capacitor.raw_value}"
            )
    for instance in circuit.instances:
        module = modules[instance.model_kind]
        ordered_nodes = [
            node_map[instance.terminals[port]]
            for port in module.ports
        ]
        resolved_parameters: list[str] = []
        for name, requested_value in instance.parameters.items():
            value = requested_value
            if value.lower() == "default":
                if name not in module.parameter_defaults:
                    raise ValueError(
                        f"{instance.name}: {name}=default but {module.path} "
                        "does not declare that parameter"
                    )
                value = module.parameter_defaults[name]
            resolved_parameters.append(f"{name}={value}")
        parameters = " ".join(resolved_parameters)
        suffix = f" {parameters}" if parameters else ""
        lines.append(
            f"X{instance.name} {' '.join(ordered_nodes)} {module.name}{suffix}"
        )
    lines.extend((f".ends {subcircuit_name}", ""))
    return "\n".join(lines)


def render_validation_deck(
    validation_output: Path,
    library_output: Path,
    subcircuit_name: str,
    ports: tuple[str, ...],
    modules: dict[str, VAModule],
) -> str:
    nodes = [f"VALIDATE_PORT_{index + 1}" for index in range(len(ports))]
    lines = [
        "AutoLDM minimal generated-include validation",
        ".option INGOLD=2",
        f'.hdl "{relative_path(modules["N"].path, validation_output)}"',
        f'.hdl "{relative_path(modules["P"].path, validation_output)}"',
        f'.include "{relative_path(library_output, validation_output)}"',
        "",
        "* Every external port is clamped to 0 V for a topology/VA compile smoke test.",
    ]
    for index, (port, node) in enumerate(zip(ports, nodes), 1):
        lines.append(f"VVALIDATE_{index} {node} 0 0 $ {port}")
    lines.extend(
        (
            f"XVALIDATE {' '.join(nodes)} {subcircuit_name}",
            ".op",
            ".end",
            "",
        )
    )
    return "\n".join(lines)

@dataclass(frozen=True)
class PexOutputs:
    pin_rc: Path
    library: Path
    validation_deck: Path
    subcircuit_name: str


def _require_file(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    return resolved


def generate_pex(
    pin_file: Path,
    c_matrix: Path,
    r_matrix: Path,
    n_model: Path,
    p_model: Path,
    output: Path,
    *,
    pin_rc_output: Path | None = None,
    validation_output: Path | None = None,
    subckt_name: str | None = None,
    md_layer: str = "MD",
    bmd_layer: str = "BMD",
    backside_prefix: str = "B",
    strict_contact_face: bool = False,
) -> PexOutputs:
    """Generate pin-level RC and PEX outputs from the complete input set."""
    pin_file = _require_file(pin_file)
    c_matrix = _require_file(c_matrix)
    r_matrix = _require_file(r_matrix)
    n_model = _require_file(n_model)
    p_model = _require_file(p_model)
    output = output.resolve()
    pin_rc_output = (
        pin_rc_output.resolve()
        if pin_rc_output is not None
        else output.with_name(output.stem.replace("_pex", "") + "_pin_spice.txt")
    )
    validation_output = (
        validation_output.resolve()
        if validation_output is not None
        else output.with_name(f"{output.stem}_validate.sp")
    )

    manifest = read_pin_manifest(pin_file)
    c_entries = read_matrix(c_matrix)
    r_entries = read_matrix(r_matrix)
    policy = ContactFacePolicy(
        md_layer=md_layer,
        bmd_layer=bmd_layer,
        backside_prefix=backside_prefix,
        strict=strict_contact_face,
    )
    pin_rc_text = render_spice(pin_file, manifest, c_entries, r_entries, policy)
    pin_rc_output.parent.mkdir(parents=True, exist_ok=True)
    pin_rc_output.write_text(pin_rc_text, encoding="utf-8")

    modules = {
        "N": read_va_module(n_model),
        "P": read_va_module(p_model),
    }
    circuit = read_circuit_input(pin_rc_output, modules)
    node_map = canonical_node_map(circuit)
    subcircuit_name = normalized_subcircuit_name(subckt_name or output.stem)

    output.parent.mkdir(parents=True, exist_ok=True)
    validation_output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        render_library(subcircuit_name, circuit, modules, node_map),
        encoding="utf-8",
    )
    validation_output.write_text(
        render_validation_deck(
            validation_output,
            output,
            subcircuit_name,
            circuit.ports,
            modules,
        ),
        encoding="utf-8",
    )

    print(f"R pins/edges: {len(manifest.r_pins)}/{len(manifest.r_pairs)}")
    print(f"C pins/edges: {len(manifest.c_pins)}/{len(manifest.c_pairs)}")
    print(f"Subcircuit: {subcircuit_name}")
    print(f"Wrote pin-RC: {pin_rc_output}")
    print(f"Wrote library: {output}")
    print(f"Wrote validation deck: {validation_output}")
    return PexOutputs(pin_rc_output, output, validation_output, subcircuit_name)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map extracted matrices and generate a reusable HSPICE PEX include."
    )
    parser.add_argument("pin_file", type=Path)
    parser.add_argument("c_matrix", type=Path)
    parser.add_argument("r_matrix", type=Path)
    parser.add_argument("n_model", type=Path)
    parser.add_argument("p_model", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--pin-rc-output", type=Path)
    parser.add_argument("--validation-output", type=Path)
    parser.add_argument("--subckt-name")
    parser.add_argument("--md-layer", default="MD")
    parser.add_argument("--bmd-layer", default="BMD")
    parser.add_argument("--backside-prefix", default="B")
    parser.add_argument("--strict-contact-face", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generate_pex(
        args.pin_file,
        args.c_matrix,
        args.r_matrix,
        args.n_model,
        args.p_model,
        args.output,
        pin_rc_output=args.pin_rc_output,
        validation_output=args.validation_output,
        subckt_name=args.subckt_name,
        md_layer=args.md_layer,
        bmd_layer=args.bmd_layer,
        backside_prefix=args.backside_prefix,
        strict_contact_face=args.strict_contact_face,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
