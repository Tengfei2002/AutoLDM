"""Build a self-contained interactive parameter-map HTML from Verilog-A sources."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VA = ROOT / "Hspice" / "va"
SOURCE = VA / "fusion_ic_nmos_lvt.va"
CLEAN = VA / "nmos_lvt_1.va"
OUT = VA / "parameter_network.html"

decl_re = re.compile(r"^\s*(parameter\s+)?real\s+(.+?);\s*(?://\s*(.*))?$")
assign_re = re.compile(r"^\s*([A-Za-z_]\w*)\s*=\s*(.+?);\s*(?://\s*(.*))?$")
ident_re = re.compile(r"\b[A-Za-z_]\w*\b")
KEYWORDS = {"real", "parameter", "begin", "end", "if", "else", "pow", "sqrt", "exp", "log", "abs", "max", "min"}


def parse(path: Path):
    declarations, assignments = {}, []
    for no, raw in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        code = raw.split("//", 1)[0].strip()
        dm = decl_re.match(raw)
        if dm:
            for part in dm.group(2).split(","):
                m = re.match(r"\s*([A-Za-z_]\w*)\s*(?:=\s*(.*))?$", part)
                if m:
                    declarations[m.group(1)] = {"line": no, "value": (m.group(2) or "—").strip(), "kind": "parameter" if dm.group(1) else "variable"}
        am = assign_re.match(code)
        if am:
            rhs = am.group(2)
            deps = sorted({x for x in ident_re.findall(rhs) if x not in KEYWORDS and x != am.group(1)})
            assignments.append({"target": am.group(1), "deps": deps, "line": no, "expr": code})
    return declarations, assignments


decl, assignments = parse(SOURCE)
clean_decl, _ = parse(CLEAN)
nn_weights = [k for k in decl if k.startswith("nn")]
nn_inputs = [k for k in decl if k in {"tgaa_nor", "w_nor", "l_nor"}]
nn_outputs = [k for k in decl if re.match(r"(?:sce|clm|qua|mob|cv|gidl)_output\d+$", k)]

def group_for(name: str) -> str:
    upper = name.upper()
    if any(x in upper for x in ("CAP", "CG", "CF", "QG", "QD", "QS", "CV")): return "C-V / capacitance"
    if any(x in upper for x in ("U0", "UA", "UD", "EU", "MOB", "VSAT", "ESAT")): return "Mobility / saturation"
    if any(x in upper for x in ("DVT", "ETA", "SCE", "CDSC", "PCLM", "PDIBL", "DROUT")): return "Short-channel / CLM"
    if any(x in upper for x in ("EOT", "TOX", "COX", "PHI", "VFB", "QM")): return "Electrostatics / quantum"
    if any(x in upper for x in ("L", "W", "FIN", "GAA", "NFIN", "NGAA")): return "Geometry"
    if any(x in upper for x in ("GIDL", "IGIDL")): return "GIDL"
    return "Model / intermediate"

nn_related = set(nn_weights + nn_inputs + nn_outputs)
all_params = []
for name, meta in decl.items():
    if name in nn_related or name.startswith("neuron"):
        continue
    all_params.append({"id": name, "label": name, "group": group_for(name), **meta})
all_param_ids = {p["id"] for p in all_params}
full_edges = sorted({(dep, a["target"]) for a in assignments for dep in a["deps"] if dep in all_param_ids and a["target"] in all_param_ids and dep != a["target"]})

physical = [
    ("geo", "Device geometry", ["L", "W", "NF", "TGAA", "WGAA", "NGAA", "DeltaWGAA", "DeltaTGAA"], 120, 205),
    ("oxide", "Oxide / electrostatics", ["EOT_0", "TOXP", "EOT", "cox", "coxeff"], 340, 115),
    ("sce", "Short-channel effects", ["DVTSHIFT", "DVT0_i", "ETA0_i", "cdsc", "Vth"], 595, 185),
    ("mob", "Mobility", ["U0", "U0_i", "UA_i", "EU_i", "ETAMOB_i"], 345, 345),
    ("vsat", "Velocity saturation", ["VSAT_a", "VSAT1_a", "Dvsat", "EsatCV"], 610, 355),
    ("cv", "C-V / capacitance", ["CGSO_i", "CGDO_i", "QG", "QD", "QS"], 855, 275),
    ("current", "Terminal current", ["ids", "IDS", "I(drain, source)"], 865, 465),
]

nodes = []
for ident, label, params, x, y in physical:
    present = [p for p in params if p in decl or p in clean_decl or p in {"Vth", "IDS", "ids", "I(drain, source)"}]
    if not present:
        present = params
    lines = [decl[p]["line"] for p in present if p in decl]
    nodes.append({"id": ident, "label": label, "type": "physical", "x": x, "y": y,
                  "detail": {"category": "Physical model", "parameters": present, "sourceLines": lines,
                             "summary": f"{label} module. Select it to inspect the model parameters and source locations."}})

nn_models = [
    ("nn-input", "NN normalized inputs", 145, 540, "Input normalization of geometry values", nn_inputs),
    ("nn-sce", "NN · SCE", 335, 535, "Short-channel-effect neural submodel", [x for x in nn_outputs if x.startswith("sce_")]),
    ("nn-clm", "NN · CLM / VSAT", 535, 555, "Channel-length modulation and velocity-saturation submodel", [x for x in nn_outputs if x.startswith("clm_")]),
    ("nn-quantum", "NN · Quantum / GIDL", 535, 670, "Quantum and GIDL correction submodel", [x for x in nn_outputs if x.startswith(("qua_", "gidl_"))]),
    ("nn-mob", "NN · Mobility", 735, 575, "Mobility correction submodel", [x for x in nn_outputs if x.startswith("mob_")]),
    ("nn-cv", "NN · C-V", 760, 690, "Capacitance correction submodel", [x for x in nn_outputs if x.startswith("cv_")]),
]
for ident, label, x, y, summary, outputs in nn_models:
    nodes.append({"id": ident, "label": label, "type": "nn", "x": x, "y": y,
                  "detail": {"category": "Neural-network layer", "parameters": outputs,
                             "sourceLines": [decl[p]["line"] for p in outputs if p in decl], "summary": summary}})

edges = [
    ["geo", "oxide"], ["geo", "sce"], ["geo", "mob"], ["oxide", "sce"], ["mob", "vsat"],
    ["sce", "current"], ["vsat", "current"], ["cv", "current"], ["geo", "cv"],
    ["geo", "nn-input", "nn"], ["nn-input", "nn-sce", "nn"], ["nn-input", "nn-clm", "nn"],
    ["nn-input", "nn-quantum", "nn"], ["nn-input", "nn-mob", "nn"], ["nn-input", "nn-cv", "nn"],
    ["nn-sce", "sce", "nn"], ["nn-clm", "vsat", "nn"], ["nn-quantum", "oxide", "nn"],
    ["nn-quantum", "sce", "nn"], ["nn-mob", "mob", "nn"], ["nn-cv", "cv", "nn"],
]

data = {"nodes": nodes, "edges": edges, "allParams": all_params, "fullEdges": full_edges, "stats": {"sourceDeclarations": len(decl), "cleanDeclarations": len(clean_decl), "physicalParameters": len(all_params), "weights": len(nn_weights), "outputs": len(nn_outputs), "assignments": len(assignments)}}

PAGE = r'''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NMOS 参数关系网</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#07111f;color:#dce8f5;font:14px/1.45 Inter,"Microsoft YaHei",sans-serif}.app{height:100vh;display:grid;grid-template-columns:265px 1fr 310px;grid-template-rows:64px 1fr}.top{grid-column:1/4;display:flex;align-items:center;gap:18px;padding:0 22px;border-bottom:1px solid #203248;background:#0b1728}.top h1{font-size:18px;margin:0;color:#fff}.top p{margin:0;color:#8fa9c5}.badge{margin-left:auto;color:#98f0ca;background:#123d34;border:1px solid #1d715b;border-radius:99px;padding:5px 10px;font-size:12px}.panel{padding:18px;border-right:1px solid #203248;background:#091526;overflow:auto}.right{border-right:0;border-left:1px solid #203248}.label{display:block;color:#86a3c3;font-size:12px;text-transform:uppercase;letter-spacing:.08em;margin:17px 0 7px}.label:first-child{margin-top:0}input{width:100%;border:1px solid #29435d;border-radius:8px;background:#0d1d31;color:#eaf4ff;padding:9px 10px;outline:none}input:focus{border-color:#36b7d7}button{width:100%;border:1px solid #2f506e;border-radius:8px;background:#10263d;color:#dce8f5;padding:8px;margin:4px 0;text-align:left;cursor:pointer}button:hover,button.active{background:#183c5a;border-color:#41b5d1}.legend{display:flex;align-items:center;gap:8px;margin:9px 0;color:#aac1d7}.dot{width:11px;height:11px;border-radius:50%;display:inline-block}.dot.physical{background:#45b6dc}.dot.nn{background:#be86f4}.canvas{position:relative;overflow:hidden;background:radial-gradient(circle at 45% 35%,#10233b,#07111f 62%)}svg{position:absolute;width:100%;height:100%;inset:0}.node{position:absolute;transform:translate(-50%,-50%);width:143px;min-height:52px;border:1px solid #3e6984;border-radius:10px;padding:8px 10px;background:#0d2940;color:#f2f8fc;font-weight:600;text-align:center;cursor:grab;box-shadow:0 8px 22px #0005;user-select:none}.node.nn{border-color:#8053a8;background:#271d3c}.node.dim{opacity:.13}.node.selected{outline:3px solid #f1bf55;z-index:2}.node small{display:block;font-weight:400;font-size:11px;color:#a9c6d8;margin-top:2px}.edge{stroke:#4d718f;stroke-width:2;opacity:.72}.edge.nn{stroke:#a66ee0;stroke-dasharray:6 5}.edge.dim{opacity:.08}.hint{position:absolute;bottom:18px;left:18px;background:#0c1c2ee8;border:1px solid #29435d;border-radius:9px;padding:8px 11px;color:#9db7d1;font-size:12px}.detail-title{font-size:19px;color:#fff;margin:0 0 5px}.muted{color:#91abc4;margin:0 0 14px}.chip{display:inline-block;background:#112d46;border:1px solid #2b526f;border-radius:99px;padding:3px 7px;margin:3px;font-family:ui-monospace,monospace;font-size:11px}.source{margin-top:14px;padding:10px;background:#07101d;border-radius:8px;color:#a6bed5;font-family:ui-monospace,monospace;font-size:12px;white-space:pre-wrap}.stat{padding:9px 0;border-bottom:1px solid #1d3148;color:#9db8d2}.stat b{color:#eaf4ff;float:right}.empty{color:#88a3bd;padding-top:80px;text-align:center}.toggle{display:flex;align-items:center;gap:8px;color:#b8cee1;margin:8px 0}.toggle input{width:auto}@media(max-width:960px){.app{grid-template-columns:220px 1fr;grid-template-rows:64px 1fr}.right{display:none}.top{grid-column:1/3}.node{width:120px;font-size:12px}}
</style><body><main class="app"><header class="top"><h1>NMOS 参数关系网</h1><p>融合模型 · 物理主链路与可折叠神经网络支路</p><span class="badge" id="stats"></span></header><aside class="panel"><label class="label">搜索节点</label><input id="search" placeholder="例如：Mobility、C-V、NN"><label class="label">显示范围</label><label class="toggle"><input id="nnToggle" type="checkbox"> 显示神经网络支路</label><button data-filter="all" class="active">全部物理模块</button><button data-filter="geo">几何与氧化层</button><button data-filter="mob">迁移率与速度饱和</button><button data-filter="sce">短沟道效应</button><button data-filter="cv">C-V / 寄生电容</button><button id="reset">重置视图</button><label class="label">图例</label><div class="legend"><i class="dot physical"></i>物理模型模块</div><div class="legend"><i class="dot nn"></i>神经网络子模型</div><p class="muted" style="margin-top:17px">点击节点查看参数。拖拽可调整布局；搜索会高亮匹配节点及一阶关系。</p></aside><section class="canvas" id="canvas"><svg id="svg"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#587b99"/></marker><marker id="arrowNN" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L7,3 z" fill="#a66ee0"/></marker></defs><g id="lines"></g></svg><div class="hint">拖动节点 · 单击查看关系 · 紫色虚线表示 NN 修正支路</div></section><aside class="panel right" id="detail"><div class="empty">选择一个节点，查看它的参数、来源和影响范围。</div></aside></main><script>const DATA=__DATA__;
const canvas=document.querySelector('#canvas'), svg=document.querySelector('#svg'), lines=document.querySelector('#lines'), detail=document.querySelector('#detail');let nnVisible=false,selected=null,filter='all';const cards={};document.querySelector('#stats').textContent=`${DATA.stats.sourceDeclarations} declarations · ${DATA.stats.weights} NN weights`;
function pos(n){return {x:n.x/1000*canvas.clientWidth,y:n.y/760*canvas.clientHeight}}function make(){DATA.edges.forEach((e,i)=>{const l=document.createElementNS('http://www.w3.org/2000/svg','line');l.classList.add('edge');if(e[2])l.classList.add('nn');l.dataset.a=e[0];l.dataset.b=e[1];l.setAttribute('marker-end',`url(#${e[2]?'arrowNN':'arrow'})`);lines.append(l)});DATA.nodes.forEach(n=>{const c=document.createElement('div');c.className=`node ${n.type}`;c.dataset.id=n.id;c.innerHTML=`${n.label}<small>${n.detail.parameters.length} mapped parameters</small>`;canvas.append(c);cards[n.id]=c;c.onclick=()=>select(n.id);drag(c,n)});render()}function render(){DATA.nodes.forEach(n=>{const c=cards[n.id],p=pos(n);c.style.left=p.x+'px';c.style.top=p.y+'px';const hidden=n.type==='nn'&&!nnVisible;c.style.display=hidden?'none':'';c.classList.toggle('dim',!hidden&&!visible(n))});[...lines.children].forEach((l,i)=>{const e=DATA.edges[i],a=DATA.nodes.find(n=>n.id===e[0]),b=DATA.nodes.find(n=>n.id===e[1]),pa=pos(a),pb=pos(b),hidden=(a.type==='nn'||b.type==='nn')&&!nnVisible;l.setAttribute('x1',pa.x);l.setAttribute('y1',pa.y);l.setAttribute('x2',pb.x);l.setAttribute('y2',pb.y);l.style.display=hidden?'none':'';l.classList.toggle('dim',!hidden&&(!visible(a)||!visible(b)))})}function visible(n){const q=document.querySelector('#search').value.trim().toLowerCase();if(filter!=='all'&&!n.id.includes(filter)&&!n.detail.category.toLowerCase().includes(filter)&&!n.label.toLowerCase().includes(filter))return false;if(!q)return true;const match=(n.label+' '+n.detail.parameters.join(' ')).toLowerCase().includes(q);if(match)return true;return DATA.edges.some(e=>(e[0]===n.id||e[1]===n.id)&&DATA.nodes.find(x=>x.id===(e[0]===n.id?e[1]:e[0])).label.toLowerCase().includes(q))}function select(id){selected=id;const n=DATA.nodes.find(x=>x.id===id);Object.values(cards).forEach(c=>c.classList.toggle('selected',c.dataset.id===id));const related=DATA.edges.filter(e=>e[0]===id||e[1]===id).map(e=>e[0]===id?e[1]:e[0]).map(x=>DATA.nodes.find(n=>n.id===x).label);detail.innerHTML=`<h2 class="detail-title">${n.label}</h2><p class="muted">${n.detail.category}</p><p>${n.detail.summary}</p><label class="label">关联参数 (${n.detail.parameters.length})</label><div>${n.detail.parameters.length?n.detail.parameters.map(x=>`<span class="chip">${x}</span>`).join(''):'—'}</div><label class="label">直接关系</label><p>${related.length?related.join(' → '):'—'}</p><div class="source">原始模型位置：${n.detail.sourceLines.length?'第 '+n.detail.sourceLines.join(', ')+' 行':'由模型计算链路汇总'}\n来源：fusion_ic_nmos_lvt.va</div>`}function drag(c,n){let drag=false,dx,dy;c.addEventListener('pointerdown',e=>{drag=true;c.setPointerCapture(e.pointerId);const p=pos(n);dx=e.clientX-p.x;dy=e.clientY-p.y});c.addEventListener('pointermove',e=>{if(!drag)return;const r=canvas.getBoundingClientRect();n.x=Math.max(55,Math.min(945,(e.clientX-r.left-dx)/r.width*1000));n.y=Math.max(55,Math.min(700,(e.clientY-r.top-dy)/r.height*760));render()});c.addEventListener('pointerup',()=>drag=false)}document.querySelector('#nnToggle').onchange=e=>{nnVisible=e.target.checked;render()};document.querySelector('#search').oninput=render;document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{filter=b.dataset.filter;document.querySelectorAll('[data-filter]').forEach(x=>x.classList.toggle('active',x===b));render()});document.querySelector('#reset').onclick=()=>{filter='all';document.querySelector('#search').value='';selected=null;Object.values(cards).forEach(c=>c.classList.remove('selected'));render()};addEventListener('resize',render);make();</script></body></html>'''

FULL_UI = r'''<style>
.full-control{margin-top:14px;padding-top:12px;border-top:1px solid #203248}.full-map{display:none;position:absolute;inset:0;padding:18px;min-width:980px;background:#07111f;overflow:auto}.full-map.show{display:block}.full-head{position:sticky;top:0;z-index:3;display:flex;align-items:center;gap:12px;padding:8px 10px;background:#0b1728;border:1px solid #29435d;border-radius:9px}.full-head select{background:#10263d;color:#dce8f5;border:1px solid #2f506e;border-radius:7px;padding:7px}.param-grid{display:grid;grid-template-columns:repeat(6,minmax(125px,1fr));gap:8px;padding:16px 0 38px}.param-card{background:#0d2940;border:1px solid #365f7d;border-radius:8px;padding:7px;cursor:pointer;font-family:ui-monospace,monospace;color:#eaf4ff}.param-card small{display:block;color:#94b5cd;font-family:Inter,"Microsoft YaHei",sans-serif;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.param-card.related{outline:2px solid #f1bf55;background:#193e58}.param-card.dim{opacity:.16}.edge-list{margin-top:10px}.edge-list .chip{cursor:pointer}</style><script>
(()=>{const originalCards=Object.values(cards);const control=document.createElement('div');control.className='full-control';control.innerHTML='<label class="toggle"><input id="fullToggle" type="checkbox"> 全量非 NN 参数模式</label><p class="muted">收录 '+DATA.stats.physicalParameters+' 个声明参数；点击参数查看真实上游/下游关系。</p>';document.querySelector('.panel').append(control);const map=document.createElement('div');map.className='full-map';map.innerHTML='<div class="full-head"><b>全量非神经网络参数</b><span id="fullCount" class="muted"></span><select id="groupFilter"><option value="all">全部类别</option></select></div><div class="param-grid" id="paramGrid"></div>';canvas.append(map);const groups=[...new Set(DATA.allParams.map(p=>p.group))].sort();const gf=map.querySelector('#groupFilter');groups.forEach(g=>gf.insertAdjacentHTML('beforeend',`<option value="${g}">${g}</option>`));const grid=map.querySelector('#paramGrid');function drawFull(){const q=document.querySelector('#search').value.trim().toLowerCase(),g=gf.value;grid.innerHTML='';let shown=0;DATA.allParams.forEach(p=>{const match=!q||(p.label+' '+p.group+' '+p.value).toLowerCase().includes(q);const ok=(g==='all'||p.group===g)&&match;if(ok)shown++;const c=document.createElement('div');c.className='param-card'+(ok?'':' dim');c.dataset.id=p.id;c.innerHTML=`${p.label}<small>${p.group} · L${p.line}</small>`;c.onclick=()=>selectParam(p.id);grid.append(c)});map.querySelector('#fullCount').textContent=`显示 ${shown} / ${DATA.allParams.length}`}
function selectParam(id){const p=DATA.allParams.find(x=>x.id===id);const up=DATA.fullEdges.filter(e=>e[1]===id).map(e=>e[0]);const down=DATA.fullEdges.filter(e=>e[0]===id).map(e=>e[1]);grid.querySelectorAll('.param-card').forEach(c=>c.classList.toggle('related',c.dataset.id===id||up.includes(c.dataset.id)||down.includes(c.dataset.id)));detail.innerHTML=`<h2 class="detail-title">${p.label}</h2><p class="muted">${p.group} · ${p.kind}</p><div class="source">默认值：${p.value}\n原始模型：fusion_ic_nmos_lvt.va，第 ${p.line} 行</div><label class="label">上游依赖 (${up.length})</label><div class="edge-list">${up.length?up.map(x=>`<span class="chip">${x}</span>`).join(''):'无显式赋值依赖'}</div><label class="label">下游影响 (${down.length})</label><div class="edge-list">${down.length?down.map(x=>`<span class="chip">${x}</span>`).join(''):'当前解析范围内未发现'}</div>`}
document.querySelector('#fullToggle').onchange=e=>{const on=e.target.checked;map.classList.toggle('show',on);originalCards.forEach(c=>c.style.display=on?'none':'');svg.style.display=on?'none':'';if(on)drawFull()};gf.onchange=drawFull;document.querySelector('#search').addEventListener('input',()=>{if(map.classList.contains('show'))drawFull()});})();</script>'''
rendered = PAGE.replace("__DATA__", json.dumps(data, ensure_ascii=False)).replace("</body>", FULL_UI + "</body>")
OUT.write_text(rendered, encoding="utf-8")
print(f"Wrote {OUT} ({len(nodes)} overview nodes, {len(all_params)} full physical parameters, {len(full_edges)} full edges)")
