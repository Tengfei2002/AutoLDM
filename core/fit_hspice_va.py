from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares


BASE = Path(__file__).resolve().parent
REF_DIR = BASE.parent / "resources" / "reference_iv"
OUTPUT_DIR = BASE.parent.parent / "LDM_local" / "fitting"
N_TEMPLATE = BASE.parent / "configs/minimal_inv/inputs/n_va.va"
P_TEMPLATE = BASE.parent / "configs/minimal_inv/inputs/p_va.va"
FIT_PROFILE = "standard"
HSPICE_DEFAULT = Path(
    r"C:\synopsys\Hspice_P-2019.06-SP1-1\WIN64\hspice.com"
)

FIXED_L_M = 16.0e-9
FIXED_W_M = 25.0e-9
FIXED_TGAA_M = 5.0e-9
FIXED_NGAA = 3.0
FIXED_NF = 1.0
NOMINAL_WEFF_UM = 2.0 * (FIXED_W_M + FIXED_TGAA_M) * FIXED_NGAA * 1.0e6

PARAMETER_NAMES = (
    "U0",
    "XL",
    "DVTSHIFT",
    "DeltaWGAA",
    "DeltaTGAA",
    "EOT_0",
)


@dataclass(frozen=True)
class Curve:
    vd: float
    vg: np.ndarray
    current_density: np.ndarray
    source: str


@dataclass(frozen=True)
class FitParameters:
    u0: float
    xl_m: float
    dvtshift: float
    delta_w_m: float
    delta_t_m: float
    eot_m: float

    @property
    def effective_lg_m(self) -> float:
        return FIXED_L_M + self.xl_m

    def as_dict(self) -> dict[str, float]:
        return {
            "U0": self.u0,
            "XL": self.xl_m,
            "DVTSHIFT": self.dvtshift,
            "DeltaWGAA": self.delta_w_m,
            "DeltaTGAA": self.delta_t_m,
            "EOT_0": self.eot_m,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fit the NFET/PFET Verilog-A models to CPP44/CPP48 Id-Vg CSV data with HSPICE."
    )
    parser.add_argument("--ref-dir", type=Path, default=REF_DIR, help="Replaceable reference-IV CSV directory")
    parser.add_argument("--n-va", type=Path, default=N_TEMPLATE, help="NFET template")
    parser.add_argument("--p-va", type=Path, default=P_TEMPLATE, help="PFET template")
    parser.add_argument(
        "--hspice",
        type=Path,
        default=HSPICE_DEFAULT,
        help="Path to hspice.com (console executable).",
    )
    parser.add_argument(
        "--max-nfev",
        type=int,
        default=60,
        help="Maximum residual evaluations reported by scipy for each independent fit.",
    )
    parser.add_argument(
        "--keep-work",
        action="store_true",
        help="Keep temporary HSPICE files for debugging.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Use parameters in fitted_va/fit_report.json as the initial point.",
    )
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="Compile the four fitted VA files and regenerate only the comparison plot.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory. Defaults to fitted_va, or fitted_va_min_xl in minimum-XL mode.",
    )
    parser.add_argument(
        "--resume-report",
        type=Path,
        default=None,
        help="Use a specified existing fit_report.json as the initial point.",
    )
    parser.add_argument(
        "--minimize-xl",
        action="store_true",
        help="Constrain XL near zero and minimize its absolute value.",
    )
    parser.add_argument(
        "--xl-limit-nm",
        type=float,
        default=1.0e-3,
        help="Maximum absolute XL in nm for --minimize-xl (default: 0.001 nm).",
    )
    return parser.parse_args()


def load_curve(device: str, cpp_nm: int, vd: float) -> Curve:
    vd_token = f"{vd:.2f}".replace(".", "_")
    path = REF_DIR / f"{device.lower()}_idvg_{vd_token}V_{cpp_nm}nm.csv"
    vg: list[float] = []
    current: list[float] = []
    with path.open(newline="", encoding="utf-8-sig") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None or reader.fieldnames[:2] != ["Vg", "Id"]:
            raise ValueError(f"{path} must start with Vg,Id")
        for row in reader:
            vg.append(float(row["Vg"]))
            current.append(abs(float(row["Id"])))
    order = np.argsort(vg)
    return Curve(
        vd=vd,
        vg=np.asarray(vg, dtype=float)[order],
        current_density=np.asarray(current, dtype=float)[order],
        source=path.name,
    )


def decode_parameters(q: np.ndarray) -> FitParameters:
    return FitParameters(
        u0=3.0e-2 * float(q[0]),
        xl_m=(12.0 * float(q[1])) * 1.0e-9,
        dvtshift=-0.5 + 0.5 * float(q[2]),
        delta_w_m=(-10.0 + 10.0 * float(q[3])) * 1.0e-9,
        delta_t_m=(-4.0 + 4.0 * float(q[4])) * 1.0e-9,
        eot_m=(0.79 * float(q[5])) * 1.0e-9,
    )


def encode_initial_parameters() -> np.ndarray:
    return np.ones(6, dtype=float)


def encode_parameters(params: FitParameters) -> np.ndarray:
    return np.asarray(
        [
            params.u0 / 3.0e-2,
            params.xl_m * 1.0e9 / 12.0,
            (params.dvtshift + 0.5) / 0.5,
            (params.delta_w_m * 1.0e9 + 10.0) / 10.0,
            (params.delta_t_m * 1.0e9 + 4.0) / 4.0,
            params.eot_m * 1.0e9 / 0.79,
        ],
        dtype=float,
    )


def parameters_from_mapping(values: dict[str, float]) -> FitParameters:
    return FitParameters(
        u0=float(values["U0"]),
        xl_m=float(values["XL"]),
        dvtshift=float(values["DVTSHIFT"]),
        delta_w_m=float(values["DeltaWGAA"]),
        delta_t_m=float(values["DeltaTGAA"]),
        eot_m=float(values["EOT_0"]),
    )


LOWER_BOUNDS = np.asarray(
    [0.001 / 0.03, -4.0 / 12.0, -1.0, -0.5, -0.125, 0.20 / 0.79],
    dtype=float,
)
UPPER_BOUNDS = np.asarray(
    [0.10 / 0.03, 84.0 / 12.0, 3.0, 3.0, 3.5, 3.00 / 0.79],
    dtype=float,
)


def hspice_number(value: float) -> str:
    return f"{value:.12e}"


def make_netlist(
    template_path: Path,
    module_name: str,
    device: str,
    params: FitParameters,
    vg_start: float,
    vg_stop: float,
    vg_step: float,
) -> str:
    polarity = 1.0 if device == "NFET" else -1.0
    parameter_text = " ".join(
        [
            f"U0={hspice_number(params.u0)}",
            f"XL={hspice_number(params.xl_m)}",
            f"DVTSHIFT={hspice_number(params.dvtshift)}",
            f"DeltaWGAA={hspice_number(params.delta_w_m)}",
            f"DeltaTGAA={hspice_number(params.delta_t_m)}",
            f"EOT_0={hspice_number(params.eot_m)}",
        ]
    )
    return "\n".join(
        [
            f"* {device} HSPICE Id-Vg fitting evaluation",
            ".option post=0 nomod numdgt=8",
            f'.hdl "{template_path.as_posix()}"',
            "",
            f"VD05 D05 0 {polarity * 0.05:.12g}",
            f"VD70 D70 0 {polarity * 0.70:.12g}",
            "VG G 0 0",
            "VS S 0 0",
            "VB B 0 0",
            f"XDUT05 D05 G S B {module_name} {parameter_text}",
            f"XDUT70 D70 G S B {module_name} {parameter_text}",
            "",
            f".dc VG {vg_start:.12g} {vg_stop:.12g} {vg_step:.12g}",
            ".print dc V(G) I(VD05) I(VD70)",
            ".end",
            "",
        ]
    )


SUFFIX_SCALE = {
    "": 1.0,
    "a": 1.0e-18,
    "f": 1.0e-15,
    "p": 1.0e-12,
    "n": 1.0e-9,
    "u": 1.0e-6,
    "m": 1.0e-3,
    "k": 1.0e3,
    "meg": 1.0e6,
    "g": 1.0e9,
    "t": 1.0e12,
}
NUMBER_RE = re.compile(
    r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)([A-Za-z]*)$"
)


def parse_hspice_number(token: str) -> float:
    match = NUMBER_RE.match(token.strip())
    if not match:
        raise ValueError(token)
    suffix = match.group(2).lower()
    if suffix not in SUFFIX_SCALE:
        raise ValueError(token)
    return float(match.group(1)) * SUFFIX_SCALE[suffix]


def parse_dc_table(lis_path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    text = lis_path.read_text(encoding="utf-8", errors="replace")
    if "**error**" in text.lower() or "***** job concluded" not in text.lower():
        errors = [line.strip() for line in text.splitlines() if "error" in line.lower()]
        raise RuntimeError("; ".join(errors[-5:]) or "HSPICE did not conclude")
    inside = False
    rows: list[tuple[float, float, float]] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped == "x":
            inside = True
            continue
        if inside and stripped == "y":
            break
        if not inside:
            continue
        parts = stripped.split()
        if len(parts) < 4:
            continue
        try:
            sweep = parse_hspice_number(parts[0])
            vg = parse_hspice_number(parts[1])
            i05 = parse_hspice_number(parts[2])
            i70 = parse_hspice_number(parts[3])
        except ValueError:
            continue
        if abs(sweep - vg) > 5.0e-6:
            continue
        rows.append((vg, i05, i70))
    if len(rows) < 10:
        raise RuntimeError(f"Could not parse the DC table in {lis_path}")
    data = np.asarray(rows, dtype=float)
    order = np.argsort(data[:, 0])
    data = data[order]
    return data[:, 0], data[:, 1], data[:, 2]


class HspiceEvaluator:
    def __init__(
        self,
        hspice: Path,
        template_path: Path,
        module_name: str,
        device: str,
        cpp_nm: int,
        curves: list[Curve],
        work_dir: Path,
        xl_target_nm: float = 12.0,
        xl_regularization_scale_nm: float = 30.0,
        xl_regularization_weight: float = 0.01,
    ) -> None:
        self.hspice = hspice
        self.template_path = template_path
        self.module_name = module_name
        self.device = device
        self.cpp_nm = cpp_nm
        self.curves = curves
        self.work_dir = work_dir
        self.xl_target_nm = xl_target_nm
        self.xl_regularization_scale_nm = xl_regularization_scale_nm
        self.xl_regularization_weight = xl_regularization_weight
        self.netlist_path = work_dir / "fit.sp"
        self.output_prefix = work_dir / "fit"
        self.evaluations = 0
        self.cache: dict[tuple[float, ...], tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        all_vg = np.concatenate([curve.vg for curve in curves])
        self.vg_start = math.floor((float(all_vg.min()) - 0.02) / 0.005) * 0.005
        self.vg_stop = math.ceil((float(all_vg.max()) + 0.02) / 0.005) * 0.005
        self.vg_step = 0.005

    def simulate(self, q: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        key = tuple(round(float(value), 10) for value in q)
        if key in self.cache:
            return self.cache[key]
        params = decode_parameters(q)
        netlist = make_netlist(
            self.template_path,
            self.module_name,
            self.device,
            params,
            self.vg_start,
            self.vg_stop,
            self.vg_step,
        )
        self.netlist_path.write_text(netlist, encoding="ascii")
        completed = subprocess.run(
            [
                str(self.hspice),
                "-i",
                str(self.netlist_path),
                "-o",
                str(self.output_prefix),
            ],
            cwd=self.work_dir,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        lis_path = self.output_prefix.with_suffix(".lis")
        if completed.returncode != 0 or not lis_path.exists():
            message = (completed.stdout + "\n" + completed.stderr)[-3000:]
            raise RuntimeError(f"HSPICE failed ({completed.returncode}): {message}")
        vg, i05, i70 = parse_dc_table(lis_path)
        # HSPICE returns A. Divide by the fixed nominal model width to compare with A/um CSV data.
        j05 = np.abs(i05) / NOMINAL_WEFF_UM
        j70 = np.abs(i70) / NOMINAL_WEFF_UM
        self.evaluations += 1
        if self.evaluations == 1 or self.evaluations % 10 == 0:
            print(
                f"[{self.device} CPP{self.cpp_nm}] HSPICE evaluation {self.evaluations}: "
                f"U0={params.u0:.4g}, XL={params.xl_m * 1e9:.3g} nm, "
                f"DVT={params.dvtshift:.3g} V, dW={params.delta_w_m * 1e9:.3g} nm, "
                f"dT={params.delta_t_m * 1e9:.3g} nm, EOT={params.eot_m * 1e9:.3g} nm",
                flush=True,
            )
        self.cache[key] = (vg, j05, j70)
        return self.cache[key]

    def residuals(self, q: np.ndarray) -> np.ndarray:
        try:
            vg, j05, j70 = self.simulate(q)
            predicted_by_vd = {0.05: j05, 0.70: j70}
            result: list[np.ndarray] = []
            for curve in self.curves:
                predicted = np.interp(curve.vg, vg, predicted_by_vd[curve.vd])
                target = curve.current_density
                floor = 1.0e-13
                log_error = np.log10(np.maximum(predicted, floor)) - np.log10(
                    np.maximum(target, floor)
                )
                linear_error = 0.80 * (predicted - target) / max(float(target.max()), floor)
                result.extend([log_error, linear_error])
            params = decode_parameters(q)
            regularization = np.asarray(
                [
                    0.02 * math.log(max(params.u0, 1e-9) / 3.0e-2),
                    self.xl_regularization_weight
                    * (params.xl_m * 1e9 - self.xl_target_nm)
                    / self.xl_regularization_scale_nm,
                    0.01 * params.dvtshift / 0.2,
                    0.02 * params.delta_w_m * 1e9 / 5.0,
                    0.02 * params.delta_t_m * 1e9 / 2.0,
                    0.02 * (params.eot_m * 1e9 - 0.79) / 0.4,
                ],
                dtype=float,
            )
            result.append(regularization)
            return np.concatenate(result)
        except Exception as exc:
            point_count = sum(curve.vg.size for curve in self.curves)
            print(f"[{self.device} CPP{self.cpp_nm}] rejected evaluation: {exc}", flush=True)
            return np.full(2 * point_count + 6, 25.0, dtype=float)


def curve_metrics(
    curve: Curve,
    sim_vg: np.ndarray,
    sim_density: np.ndarray,
) -> dict[str, float | int | str]:
    predicted = np.interp(curve.vg, sim_vg, sim_density)
    floor = 1.0e-13
    log_error = np.log10(np.maximum(predicted, floor)) - np.log10(
        np.maximum(curve.current_density, floor)
    )
    on_index = int(np.argmax(curve.current_density))
    on_relative = (
        predicted[on_index] / curve.current_density[on_index] - 1.0
    ) * 100.0
    return {
        "source": curve.source,
        "point_count": int(curve.vg.size),
        "log_rmse_decades": float(np.sqrt(np.mean(log_error**2))),
        "log_mae_decades": float(np.mean(np.abs(log_error))),
        "max_abs_log_error_decades": float(np.max(np.abs(log_error))),
        "on_current_relative_error_percent": float(on_relative),
    }


def fit_corner(
    hspice: Path,
    device: str,
    cpp_nm: int,
    max_nfev: int,
    work_root: Path,
    initial: np.ndarray | None = None,
    lower_bounds: np.ndarray = LOWER_BOUNDS,
    upper_bounds: np.ndarray = UPPER_BOUNDS,
    xl_target_nm: float = 12.0,
    xl_regularization_scale_nm: float = 30.0,
    xl_regularization_weight: float = 0.01,
) -> tuple[FitParameters, dict[str, object], tuple[np.ndarray, np.ndarray, np.ndarray]]:
    template_path = N_TEMPLATE if device == "NFET" else P_TEMPLATE
    module_name = "nmos_lvt" if device == "NFET" else "pmos_lvt"
    curves = [load_curve(device, cpp_nm, 0.05), load_curve(device, cpp_nm, 0.70)]
    work_dir = work_root / f"{device.lower()}_cpp{cpp_nm}"
    work_dir.mkdir(parents=True, exist_ok=True)
    evaluator = HspiceEvaluator(
        hspice=hspice,
        template_path=template_path,
        module_name=module_name,
        device=device,
        cpp_nm=cpp_nm,
        curves=curves,
        work_dir=work_dir,
        xl_target_nm=xl_target_nm,
        xl_regularization_scale_nm=xl_regularization_scale_nm,
        xl_regularization_weight=xl_regularization_weight,
    )
    if initial is None:
        initial = encode_initial_parameters()
    span = upper_bounds - lower_bounds
    initial = np.minimum(
        upper_bounds - 1.0e-9 * span,
        np.maximum(lower_bounds + 1.0e-9 * span, initial),
    )
    initial_residual = evaluator.residuals(initial)
    print(
        f"[{device} CPP{cpp_nm}] initial RMS residual={np.sqrt(np.mean(initial_residual**2)):.4g}",
        flush=True,
    )
    result = least_squares(
        evaluator.residuals,
        initial,
        bounds=(lower_bounds, upper_bounds),
        method="trf",
        loss="soft_l1",
        f_scale=0.20,
        diff_step=2.0e-3,
        x_scale=np.ones(6),
        max_nfev=max_nfev,
        ftol=1.0e-4,
        xtol=1.0e-4,
        gtol=1.0e-4,
        verbose=0,
    )
    best_params = decode_parameters(result.x)
    sim_vg, sim_j05, sim_j70 = evaluator.simulate(result.x)
    metrics = {
        "fit_profile": FIT_PROFILE,
        "success": bool(result.success),
        "termination": str(result.message),
        "scipy_nfev": int(result.nfev),
        "hspice_evaluations": int(evaluator.evaluations),
        "cost": float(result.cost),
        "optimality": float(result.optimality),
        "parameters": best_params.as_dict(),
        "effective_Lg_nm": best_params.effective_lg_m * 1.0e9,
        "curves": {
            "Vd_0.05": curve_metrics(curves[0], sim_vg, sim_j05),
            "Vd_0.70": curve_metrics(curves[1], sim_vg, sim_j70),
        },
    }
    print(
        f"[{device} CPP{cpp_nm}] complete: cost={result.cost:.5g}, "
        f"nfev={result.nfev}, HSPICE={evaluator.evaluations}",
        flush=True,
    )
    return best_params, metrics, (sim_vg, sim_j05, sim_j70)


def load_resume_points(
    report_path: Path | None = None,
) -> dict[tuple[str, int], np.ndarray]:
    if report_path is None:
        report_path = OUTPUT_DIR / "fit_report.json"
    if not report_path.is_file():
        return {}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    points: dict[tuple[str, int], np.ndarray] = {}
    for device, cpp_nm in [("NFET", 44), ("PFET", 44), ("PFET", 48)]:
        values = report["corners"][f"{device}_CPP{cpp_nm}"]["parameters"]
        params = parameters_from_mapping(values)
        points[(device, cpp_nm)] = encode_parameters(params)
    return points


def replace_parameter(text: str, name: str, value: float) -> str:
    pattern = re.compile(
        rf"^(\s*parameter\s+real\s+{re.escape(name)}\s*=\s*)[^;]+;",
        flags=re.MULTILINE,
    )
    replacement = rf"\g<1>{value:.12e};"
    updated, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        raise RuntimeError(f"Expected one top-level parameter declaration for {name}")
    return updated


def write_fitted_model(
    device: str,
    cpp_nm: int,
    params: FitParameters,
    metrics: dict[str, object],
) -> Path:
    template_path = N_TEMPLATE if device == "NFET" else P_TEMPLATE
    text = template_path.read_text(encoding="utf-8")
    include_marker = '`include "constants.vams"'
    include_index = text.find(include_marker)
    if include_index < 0:
        raise RuntimeError(f"Could not find {include_marker} in {template_path}")
    reference_files = ", ".join(
        str(curve["source"])
        for curve in (metrics["curves"]["Vd_0.05"], metrics["curves"]["Vd_0.70"])
    )
    header = "\n".join(
        [
            "//*********************************************************************//",
            f"//* PKU PHIMO-Fusion {device} - HSPICE Id-Vg fit, CPP={cpp_nm} nm      *//",
            "//*********************************************************************//",
            "// Copyright 2025 Peking University, Shenzhen. All rights reserved.",
            "// Original model authors: Baokang Peng, Guoyao Cheng, Wu Dai,",
            "// Fangxing Zhang, Yu Li, Honglin Wu.",
            "// Reference: B. Peng et al., PHIMO-NN: Compact Modeling by Fusing",
            "// Device Physics and Neural Networks for One-Shot Parameterization,",
            "// IEEE TCAD; physics core derived from BSIM-CMG version 111.2.1.",
            f"// Fit target: {reference_files} (current density in A/um).",
            "// HSPICE fit uses Vd=0.05 V and 0.70 V simultaneously.",
            f"// Fixed geometry: L=16 nm, W=25 nm, TGAA=5 nm, NGAA=3, NF=1.",
            f"// Nominal current-normalization width: {NOMINAL_WEFF_UM:.6g} um.",
            "// Fitted parameters: U0, XL, DVTSHIFT, DeltaWGAA, DeltaTGAA, EOT_0.",
            f"// Fitted effective Lg=L+XL: {params.effective_lg_m * 1e9:.6g} nm.",
            f"// Fit profile: {metrics.get('fit_profile', 'standard')}.",
            "// This calibration is for DC Id-Vg only; capacitance was not fitted.",
            "// Fitted values are numerical corner parameters; see ../fit_report.json.",
            "//*********************************************************************//",
            "",
        ]
    )
    text = header + text[include_index:]
    for name, value in params.as_dict().items():
        text = replace_parameter(text, name, value)
    corner_dir = OUTPUT_DIR / f"cpp{cpp_nm}"
    corner_dir.mkdir(parents=True, exist_ok=True)
    output_path = corner_dir / ("test_fet_n.va" if device == "NFET" else "test_fet_p.va")
    output_path.write_text(text, encoding="utf-8", newline="\n")
    return output_path


def plot_fits(
    fit_data: dict[tuple[str, int], tuple[FitParameters, dict[str, object], tuple[np.ndarray, np.ndarray, np.ndarray]]]
) -> Path:
    plt.rcParams.update(
        {
            "font.family": "Arial",
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 10,
            "legend.fontsize": 8,
            "axes.linewidth": 0.9,
            "lines.linewidth": 1.6,
        }
    )
    fig, axes = plt.subplots(
        2, 2, figsize=(9.0, 6.8), sharey=True, layout="constrained"
    )
    colors = {0.05: "#1f77b4", 0.70: "#d95f02"}
    for axis, (device, cpp_nm) in zip(
        axes.flat,
        [("NFET", 44), ("NFET", 48), ("PFET", 44), ("PFET", 48)],
        strict=True,
    ):
        _, metrics, simulation = fit_data[(device, cpp_nm)]
        sim_vg, sim_j05, sim_j70 = simulation
        for vd, sim_density in [(0.05, sim_j05), (0.70, sim_j70)]:
            curve = load_curve(device, cpp_nm, vd)
            axis.semilogy(
                curve.vg,
                curve.current_density,
                linestyle="none",
                marker="o" if vd == 0.05 else "s",
                markersize=3.4,
                markerfacecolor="white",
                markeredgewidth=0.9,
                color=colors[vd],
                label=f"CSV Vd={vd:.2f} V",
            )
            axis.semilogy(
                sim_vg,
                sim_density,
                color=colors[vd],
                label=f"HSPICE Vd={vd:.2f} V",
            )
        p = metrics["parameters"]
        axis.set_title(
            f"{device}, CPP={cpp_nm} nm\n"
            f"U0={p['U0']:.3g}, XL={p['XL'] * 1e9:.3g} nm, DVT={p['DVTSHIFT']:.3g} V"
        )
        axis.set_xlabel("Vg (V)")
        axis.grid(True, which="major", color="0.78", linewidth=0.6)
        axis.grid(True, which="minor", color="0.90", linewidth=0.4)
        axis.tick_params(direction="in", which="both", top=True, right=True)
        axis.legend(loc="best", frameon=True)
    axes[0, 0].set_ylabel("|Id| (A/um)")
    axes[1, 0].set_ylabel("|Id| (A/um)")
    title_prefix = "Minimum-|XL| " if FIT_PROFILE == "minimum_abs_XL" else ""
    fig.suptitle(
        f"{title_prefix}HSPICE Verilog-A fits to CPP44/CPP48 current-density curves",
        fontsize=12,
    )
    output_path = OUTPUT_DIR / "fit_comparison.png"
    fig.savefig(output_path, dpi=250, bbox_inches="tight")
    plt.close(fig)
    return output_path


def render_and_verify_existing_models(
    hspice: Path, work_root: Path
) -> tuple[Path, int]:
    report_path = OUTPUT_DIR / "fit_report.json"
    if not report_path.is_file():
        raise FileNotFoundError(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    fit_data: dict[
        tuple[str, int],
        tuple[FitParameters, dict[str, object], tuple[np.ndarray, np.ndarray, np.ndarray]],
    ] = {}
    verified = 0
    for device, cpp_nm in [
        ("NFET", 44),
        ("PFET", 44),
        ("NFET", 48),
        ("PFET", 48),
    ]:
        metrics = report["corners"][f"{device}_CPP{cpp_nm}"]
        params = parameters_from_mapping(metrics["parameters"])
        model_path = OUTPUT_DIR / f"cpp{cpp_nm}" / (
            "test_fet_n.va" if device == "NFET" else "test_fet_p.va"
        )
        module_name = "nmos_lvt" if device == "NFET" else "pmos_lvt"
        curves = [load_curve(device, cpp_nm, 0.05), load_curve(device, cpp_nm, 0.70)]
        evaluator = HspiceEvaluator(
            hspice=hspice,
            template_path=model_path,
            module_name=module_name,
            device=device,
            cpp_nm=cpp_nm,
            curves=curves,
            work_dir=work_root / f"verify_{device.lower()}_cpp{cpp_nm}",
        )
        evaluator.work_dir.mkdir(parents=True, exist_ok=True)
        simulation = evaluator.simulate(encode_parameters(params))
        fit_data[(device, cpp_nm)] = (params, metrics, simulation)
        verified += 1
        print(f"[verify] compiled and simulated {model_path}", flush=True)
    return plot_fits(fit_data), verified


def main() -> int:
    global OUTPUT_DIR, FIT_PROFILE, REF_DIR, N_TEMPLATE, P_TEMPLATE
    args = parse_args()
    REF_DIR = args.ref_dir.resolve()
    N_TEMPLATE = args.n_va.resolve()
    P_TEMPLATE = args.p_va.resolve()
    if args.xl_limit_nm <= 0:
        raise ValueError("--xl-limit-nm must be positive")
    if args.output_dir is None:
        OUTPUT_DIR = OUTPUT_DIR / ("minimum_xl" if args.minimize_xl else "standard")
    else:
        candidate = args.output_dir
        OUTPUT_DIR = candidate.resolve()
    if OUTPUT_DIR.resolve().is_relative_to(BASE.parent):
        raise ValueError("Fitting output must be outside the upload directory")
    FIT_PROFILE = "minimum_abs_XL" if args.minimize_xl else "standard"
    hspice = args.hspice.resolve()
    if not hspice.is_file():
        raise FileNotFoundError(hspice)
    for required in [N_TEMPLATE, P_TEMPLATE]:
        if not required.is_file():
            raise FileNotFoundError(required)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if args.keep_work:
        temp_context = None
        work_root = Path(tempfile.mkdtemp(prefix="autoldm_fit_", dir=OUTPUT_DIR))
    else:
        temp_context = tempfile.TemporaryDirectory(prefix="autoldm_fit_")
        work_root = Path(temp_context.name)
    print(f"[setup] HSPICE={hspice}", flush=True)
    print(
        f"[setup] fixed nominal width={NOMINAL_WEFF_UM:.6g} um; "
        "all comparisons are in A/um",
        flush=True,
    )
    if args.render_only:
        try:
            comparison_path, verified = render_and_verify_existing_models(
                hspice, work_root
            )
            print(f"[verify] models={verified}", flush=True)
            print(f"[done] plot={comparison_path}", flush=True)
        finally:
            if temp_context is not None:
                temp_context.cleanup()
        return 0
    resume_report = args.resume_report.resolve() if args.resume_report else None
    resume_points = (
        load_resume_points(resume_report)
        if (args.resume or resume_report is not None)
        else {}
    )
    lower_bounds = LOWER_BOUNDS.copy()
    upper_bounds = UPPER_BOUNDS.copy()
    xl_target_nm = 12.0
    xl_scale_nm = 30.0
    xl_weight = 0.01
    if args.minimize_xl:
        lower_bounds[1] = -args.xl_limit_nm / 12.0
        upper_bounds[1] = args.xl_limit_nm / 12.0
        xl_target_nm = 0.0
        xl_scale_nm = args.xl_limit_nm
        xl_weight = 0.25
        for point in resume_points.values():
            point[1] = 0.0
    fit_data: dict[
        tuple[str, int],
        tuple[FitParameters, dict[str, object], tuple[np.ndarray, np.ndarray, np.ndarray]],
    ] = {}
    try:
        nfet_fit = fit_corner(
            hspice=hspice,
            device="NFET",
            cpp_nm=44,
            max_nfev=args.max_nfev,
            work_root=work_root,
            initial=resume_points.get(("NFET", 44)),
            lower_bounds=lower_bounds,
            upper_bounds=upper_bounds,
            xl_target_nm=xl_target_nm,
            xl_regularization_scale_nm=xl_scale_nm,
            xl_regularization_weight=xl_weight,
        )
        fit_data[("NFET", 44)] = nfet_fit
        # CPP44 and CPP48 NFET reference data are exactly identical.
        n_params, n_metrics_44, n_sim = nfet_fit
        n_metrics_48 = json.loads(json.dumps(n_metrics_44))
        n_metrics_48["curves"] = {
            "Vd_0.05": curve_metrics(load_curve("NFET", 48, 0.05), n_sim[0], n_sim[1]),
            "Vd_0.70": curve_metrics(load_curve("NFET", 48, 0.70), n_sim[0], n_sim[2]),
        }
        n_metrics_48["note"] = "Reused CPP44 NFET fit because CPP44/CPP48 CSV curves are identical."
        fit_data[("NFET", 48)] = (n_params, n_metrics_48, n_sim)

        for cpp_nm in (44, 48):
            fit_data[("PFET", cpp_nm)] = fit_corner(
                hspice=hspice,
                device="PFET",
                cpp_nm=cpp_nm,
                max_nfev=args.max_nfev,
                work_root=work_root,
                initial=resume_points.get(("PFET", cpp_nm)),
                lower_bounds=lower_bounds,
                upper_bounds=upper_bounds,
                xl_target_nm=xl_target_nm,
                xl_regularization_scale_nm=xl_scale_nm,
                xl_regularization_weight=xl_weight,
            )

        output_models: list[str] = []
        report: dict[str, object] = {
            "title": "HSPICE Verilog-A Id-Vg fits for CPP44 and CPP48",
            "fit_profile": FIT_PROFILE,
            "preserved_previous_results": bool(args.minimize_xl),
            "initial_report": str(resume_report) if resume_report else None,
            "reference_current_unit": "A/um",
            "hspice_output_unit": "A",
            "current_density_conversion": "abs(I_HSPICE_A) / nominal_model_Weff_um",
            "nominal_model_Weff_um": NOMINAL_WEFF_UM,
            "fixed_parameters": {
                "L": FIXED_L_M,
                "W": FIXED_W_M,
                "TGAA": FIXED_TGAA_M,
                "NGAA": FIXED_NGAA,
                "NF": FIXED_NF,
                "NBODY": 1.0e21,
                "NSD": 3.0e26,
                "PHIG_NFET": 4.38,
                "PHIG_PFET": 4.67,
            },
            "fitted_parameters": list(PARAMETER_NAMES),
            "fit_bounds": {
                "U0": [1.0e-3, 1.0e-1],
                "XL_nm": [
                    float(12.0 * lower_bounds[1]),
                    float(12.0 * upper_bounds[1]),
                ],
                "DVTSHIFT_V": [-1.0, 1.0],
                "DeltaWGAA_nm": [-15.0, 20.0],
                "DeltaTGAA_nm": [-4.5, 10.0],
                "EOT_0_nm": [0.2, 3.0],
            },
            "reference_metadata": {
                "Lg_nm": 12,
                "corner_dimension": "CPP_nm",
                "normalized_backup_unit": "dimensionless",
            },
            "limitations": [
                "Only DC Id-Vg was fitted; charge and capacitance behavior was not calibrated.",
                "The selected six parameters do not provide an independent DIBL/high-field control, so PFET Vd=0.70 V retains a larger residual than the other curves.",
                "Parameters that reach a fit bound should be interpreted as numerical corner values rather than uniquely extracted physical quantities.",
            ],
            "corners": {},
        }
        for device, cpp_nm in [
            ("NFET", 44),
            ("PFET", 44),
            ("NFET", 48),
            ("PFET", 48),
        ]:
            params, metrics, _ = fit_data[(device, cpp_nm)]
            model_path = write_fitted_model(device, cpp_nm, params, metrics)
            output_models.append(str(model_path.relative_to(BASE)))
            report["corners"][f"{device}_CPP{cpp_nm}"] = metrics
        report["output_models"] = output_models
        comparison_path = plot_fits(fit_data)
        report["comparison_plot"] = str(comparison_path.relative_to(BASE))
        report_path = OUTPUT_DIR / "fit_report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"[done] models={len(output_models)}", flush=True)
        print(f"[done] report={report_path}", flush=True)
        print(f"[done] plot={comparison_path}", flush=True)
    finally:
        if args.keep_work:
            print(f"[debug] kept HSPICE work directory: {work_root}", flush=True)
        elif temp_context is not None:
            temp_context.cleanup()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
