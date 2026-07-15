import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "file:///C:/Users/Tengfei/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs";

async function writeBlob(path, blob) {
  await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer()));
}

const input = process.argv[2];
const outDir = process.argv[3];
if (!input || !outDir) {
  throw new Error("usage: node test_artifact_render.mjs <input.pptx> <outDir>");
}
await fs.mkdir(outDir, { recursive: true });
const presentation = await PresentationFile.importPptx(await FileBlob.load(input));
const inspect = await presentation.inspect({ kind: "slide,textbox,image,shape,layout", maxChars: 12000 });
await fs.writeFile(`${outDir}/inspect.ndjson`, inspect.ndjson ?? String(inspect));
let idx = 1;
for (const slide of presentation.slides.items) {
  const png = await presentation.export({ slide, format: "png", scale: 1 });
  await writeBlob(`${outDir}/slide-${String(idx).padStart(2, "0")}.png`, png);
  const layout = await slide.export({ format: "layout" });
  await fs.writeFile(`${outDir}/slide-${String(idx).padStart(2, "0")}.layout.json`, await layout.text());
  idx += 1;
}
const montage = await presentation.export({ format: "webp", montage: true, scale: 1 });
await writeBlob(`${outDir}/montage.webp`, montage);
console.log(`rendered ${idx - 1} slides to ${outDir}`);
