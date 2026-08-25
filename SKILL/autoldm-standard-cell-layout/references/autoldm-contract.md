# AutoLDM 版图生成与验证约定

## 适用范围

本约定用于当前仓库的矩形文本版图、GDS 转换和 SDE 结构生成。它以仓库中已经能够正常生成的参考标准单元为技术模板，不表示代工厂 PDK 签核。

默认参考文件是：

```text
FLOW/test/INPUT_MODEL/test_gds.txt
FLOW/test/INPUT_MODEL/test_params.txt
FLOW/test/INPUT_MODEL/test_stacked.txt
FLOW/test/INPUT_MODEL/test_design_rules.txt
```

如果用户指定了另一个已经通过当前 SDE 生成流程的参考单元，应使用用户指定的参考文件，不要同时混用多个参考单元的坐标体系。

## 文件命名

工程输入使用工程名称作为前缀：

```text
<name>_gds.txt
<name>.gds
<name>_params.txt
<name>_stacked.txt
<name>_design_rules.txt
<name>_fet_n.va
<name>_fet_p.va
```

标准单元专用测试输入使用逻辑单元名：

```text
sdc_pin/<cell>.txt
sdc_tb/<cell>.txt
sdc_pyscript/<cell>.py
```

不要把工程名和逻辑单元名合并为一个隐式参数。

## 文本版图格式

每个有效数据行包含：

```text
x1 y1 x2 y2 layer_num label
```

- 长度单位固定为 `um`；
- 新生成的目标版图只允许正面积矩形；
- `None` 表示无电气标签；
- 电气标签只能使用字母、数字和下划线，并以字母或下划线开头；
- 标签必须与 pin manifest、R/C matrix 和生成的 PEX 节点一致。

## 必须执行的验证

以下命令中的路径应替换为目标工程的实际路径。

### 1. 参考约定检查

```powershell
python SKILL/autoldm-standard-cell-layout/scripts/layout_contract.py validate `
  --reference FLOW/test/INPUT_MODEL/test_gds.txt `
  --candidate FLOW/<project>/INPUT_MODEL/<name>_gds.txt `
  --ports A,Y,VDD,VSS
```

出现 `ERROR` 时不得继续声明版图正确。`WARNING` 必须结合 stack 和规则说明原因。

### 2. SDE 预检查

```powershell
python FLOW/<project>/gen_sde.py `
  FLOW/<project>/INPUT_MODEL/<name>_gds.txt `
  FLOW/<project>/INPUT_MODEL/<name>_params.txt `
  FLOW/<project>/INPUT_MODEL/<name>_stacked.txt `
  --design-rules FLOW/<project>/INPUT_MODEL/<name>_design_rules.txt `
  --validate-only `
  -o FLOW/<project>/SDE/<name>_r_sde.cmd
```

### 3. GDS 转换和回读

```powershell
python FLOW/<project>/INPUT_MODEL/txt_gds_trans/txt2gds.py `
  FLOW/<project>/INPUT_MODEL/<name>_gds.txt `
  FLOW/<project>/INPUT_MODEL/<name>.gds

python FLOW/<project>/INPUT_MODEL/txt_gds_trans/gds2txt.py `
  FLOW/<project>/INPUT_MODEL/<name>.gds `
  FLOW/<project>/INPUT_MODEL/<name>_roundtrip.txt

python SKILL/autoldm-standard-cell-layout/scripts/layout_contract.py exact `
  FLOW/<project>/INPUT_MODEL/<name>_gds.txt `
  FLOW/<project>/INPUT_MODEL/<name>_roundtrip.txt
```

回读比较通过后删除临时 `*_roundtrip.txt`。

## 正确性边界

只有下列条件全部满足时，才能称为“符合当前 AutoLDM 参考约定并可生成”：

1. 逻辑拓扑与 FET 端口映射已确认；
2. reference contract 无 ERROR；
3. SDE preflight 无 ERROR；

4. GDS roundtrip 几何和标签一致；
5. pin manifest 的节点能在版图标签和后续 matrix 中对应。

不得把以上结论表述为 foundry signoff、完整 LVS 通过或真实 RC 提取完成。
