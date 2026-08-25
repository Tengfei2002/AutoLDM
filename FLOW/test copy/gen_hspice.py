#!/usr/bin/env python3
"""Generate a reusable HSPICE subcircuit from self-describing pin-RC data.

The input RC file supplies every circuit-specific fact:

    (R){...}
    R_name node1 node2 value

    (C){...}
    C_name node1 node2 value

    (FET){N1,P1,...}{S,G,D,B}
    N1 S=node G=node D=node B=node L=default W=default NF=default

    (PORT){A,Y,VDD,VSS}
    A=physical_node

No device, node, port, or circuit topology is hard-coded here.  Instance names
beginning with N use the first VA input; names beginning with P use the second.
Assignments whose value is ``default`` are resolved from the Verilog-A
``parameter`` declaration and emitted explicitly.  This preserves model
defaults while remaining compatible with older HSPICE pVA releases.
"""

from __future__ import annotations

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
    source = path.read_text(encoding="utf-8", errors="replace")
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

    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate an HSPICE .inc and generic zero-bias validation deck "
            "from VA models and a self-describing pin-RC file."
        )
    )
    parser.add_argument("n_model", type=Path, help="N-type Verilog-A file")
    parser.add_argument("p_model", type=Path, help="P-type Verilog-A file")
    parser.add_argument("rc_file", type=Path, help="Pin-RC file with FET/PORT sections")
    parser.add_argument("-o", "--output", type=Path, required=True, help="Output .inc")
    parser.add_argument(
        "--subckt-name",
        help="Optional generated subcircuit name; defaults to the output filename stem",
    )
    parser.add_argument(
        "--validation-output",
        type=Path,
        help="Validation .sp path; defaults beside the .inc as <stem>_validate.sp",
    )
    return parser.parse_args()


def validate_input_files(paths: tuple[Path, ...]) -> None:
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)


def main() -> int:
    args = parse_args()
    validate_input_files((args.n_model, args.p_model, args.rc_file))
    output = args.output.resolve()
    validation_output = (
        args.validation_output.resolve()
        if args.validation_output is not None
        else output.with_name(f"{output.stem}_validate.sp")
    )
    subcircuit_name = normalized_subcircuit_name(
        args.subckt_name if args.subckt_name else output.stem
    )
    modules = {
        "N": read_va_module(args.n_model),
        "P": read_va_module(args.p_model),
    }
    circuit = read_circuit_input(args.rc_file, modules)
    node_map = canonical_node_map(circuit)

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

    print(f"Subcircuit: {subcircuit_name}")
    print(f"Ports/FETs: {len(circuit.ports)}/{len(circuit.instances)}")
    print(f"R/C elements: {len(circuit.resistors)}/{len(circuit.capacitors)}")
    print(f"Wrote library: {output}")
    print(f"Wrote validation deck: {validation_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
