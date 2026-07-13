from pathlib import Path
import sys
import re
import pdfplumber

root = Path(".Referance_Paper/SRAM")
needle = sys.argv[1]
pages_arg = sys.argv[2] if len(sys.argv) > 2 else ""
files = [f for f in sorted(root.glob("*.pdf")) if needle.lower() in f.name.lower()]
if not files:
    raise SystemExit(f"no file for {needle}")
f = files[0]
print("FILE", f.name)
with pdfplumber.open(f) as pdf:
    if pages_arg:
        page_nums = [int(x) for x in pages_arg.split(",")]
    else:
        page_nums = list(range(1, len(pdf.pages) + 1))
    for page_num in page_nums:
        page = pdf.pages[page_num - 1]
        text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
        text = re.sub(r"\n{3,}", "\n\n", text)
        print(f"\n--- PAGE {page_num} ---")
        print(text[:6000])
