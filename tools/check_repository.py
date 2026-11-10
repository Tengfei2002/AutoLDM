"""Check the publishable source boundary without commercial dependencies."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.workspace import audit_release


def main():
    files = audit_release()
    forbidden_suffixes = {".tr0", ".sw0", ".lis", ".dll", ".valog"}
    for path in files:
        if path.suffix.lower() in forbidden_suffixes:
            raise ValueError(f"Generated simulation output must stay local: {path.name}")
        if path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example"):
            raise ValueError(f"Local environment file must not be published: {path.name}")
    print(f"PASS: {len(files)} source files; configuration checksums and size policy verified")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"Repository check failed: {exc}", file=sys.stderr)
        raise SystemExit(2)
