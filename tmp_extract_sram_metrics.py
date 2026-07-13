from pathlib import Path
import re
import pdfplumber

root = Path(".Referance_Paper/SRAM")
keywords = re.compile(
    r"(SNM|RSNM|HSNM|WSNM|write margin|read margin|Vmin|V_min|VDD|cell area|"
    r"area|nm\^?2|µm|um|read current|Iread|Ion|Ioff|delay|power|energy|"
    r"leakage|failure|sigma|yield|BER|PPA|access|hold|read|write|stability|SRAM)",
    re.I,
)

for f in sorted(root.glob("*.pdf")):
    print("\n###FILE###", f.name)
    try:
        with pdfplumber.open(f) as pdf:
            print("PAGES", len(pdf.pages))
            hits = []
            for page_index, page in enumerate(pdf.pages, 1):
                text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                lines = [
                    re.sub(r"\s+", " ", line).strip()
                    for line in text.splitlines()
                    if line.strip()
                ]
                for line in lines:
                    if keywords.search(line) and re.search(r"\d", line):
                        hits.append((page_index, line))
            for page_index, line in hits[:90]:
                print(f"p{page_index}: {line[:520]}")
            if len(hits) > 90:
                print("...HITS", len(hits))
    except Exception as exc:
        print("ERROR", type(exc).__name__, exc)
