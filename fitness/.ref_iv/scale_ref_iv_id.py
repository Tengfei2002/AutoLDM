from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd


REF_DIR = Path(__file__).resolve().parent
BACKUP_DIR = REF_DIR / "backup_before_id_scale"
SCALE = 3.9e-5 / (0.44893 * 0.156)


def main() -> int:
    csv_files = sorted(p for p in REF_DIR.glob("*.csv") if p.is_file())
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in {REF_DIR}")

    BACKUP_DIR.mkdir(exist_ok=True)
    rows = []
    for path in csv_files:
        backup_path = BACKUP_DIR / path.name
        if not backup_path.exists():
            shutil.copy2(path, backup_path)

        df = pd.read_csv(path)
        if len(df.columns) < 2:
            raise ValueError(f"{path.name} has fewer than two columns")
        first_col, second_col = df.columns[:2]
        before_min = float(pd.to_numeric(df[second_col]).min())
        before_max = float(pd.to_numeric(df[second_col]).max())
        df[second_col] = pd.to_numeric(df[second_col]) * SCALE
        after_min = float(df[second_col].min())
        after_max = float(df[second_col].max())
        df.to_csv(path, index=False)

        rows.append(
            {
                "file": path.name,
                "first_column": first_col,
                "scaled_column": second_col,
                "scale": SCALE,
                "before_min": before_min,
                "before_max": before_max,
                "after_min": after_min,
                "after_max": after_max,
                "backup": str(backup_path),
            }
        )

    summary = {
        "operation": "Id_scaled",
        "formula": "Id_scaled = Id_original / 0.44893 * 3.9E-5 / 0.156",
        "scale": SCALE,
        "backup_dir": str(BACKUP_DIR),
        "files": rows,
    }
    (REF_DIR / "id_scale_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    md_lines = [
        "# .ref_iv 第二列电流缩放记录",
        "",
        "缩放公式：",
        "",
        "```text",
        "Id_scaled = Id_original / 0.44893 * 3.9E-5 / 0.156",
        f"scale = {SCALE:.12e}",
        "```",
        "",
        f"备份目录：`{BACKUP_DIR.name}`",
        "",
        "| 文件 | 缩放前最小值 | 缩放前最大值 | 缩放后最小值 | 缩放后最大值 |",
        "|---|---:|---:|---:|---:|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['file']} | {r['before_min']:.6e} | {r['before_max']:.6e} | "
            f"{r['after_min']:.6e} | {r['after_max']:.6e} |"
        )
    (REF_DIR / "id_scale_summary.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

    print(f"[done] scale={SCALE:.12e}")
    print(f"[done] files={len(rows)}")
    print(f"[done] backup={BACKUP_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
