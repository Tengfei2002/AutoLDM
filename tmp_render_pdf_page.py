from pathlib import Path
import sys
import pypdfium2 as pdfium

root = Path(".Referance_Paper/SRAM")
needle = sys.argv[1]
page_num = int(sys.argv[2])
out_dir = Path("tmp_pdf_pages")
out_dir.mkdir(exist_ok=True)
files = [f for f in sorted(root.glob("*.pdf")) if needle.lower() in f.name.lower()]
if not files:
    raise SystemExit(f"no file for {needle}")
pdf_path = files[0]
doc = pdfium.PdfDocument(str(pdf_path))
page = doc[page_num - 1]
bitmap = page.render(scale=3).to_pil()
out = out_dir / f"{needle}_p{page_num}.png"
bitmap.save(out)
print(out)
