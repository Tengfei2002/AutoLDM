# 可替换配置包契约 v1

每套配置用一个 `profile.json` 描述。路径相对声明该路径的清单文件解析，不依赖命令执行目录。包内文件可以引用包内子目录或共享资源；公共最小包必须全部落在上传目录内。本地配置可引用其他存储，但建议 `fork` 为独立包后归档。

```json
{
  "schema_version": 1,
  "id": "inv_new_bench",
  "version": "1",
  "cell": "inv",
  "extends": "../minimal_inv/profile.json",
  "files": {"bench": "inputs/bench.txt"},
  "sha256": {"bench": "替换为该文件的64位SHA256"}
}
```

继承可以替换工艺参数、层叠、规则、模型、版图、连接、测试条件、适配器和矩阵。父包路径仍相对父清单解析。新文件必须提供自己的校验值；不会继承旧文件哈希。循环继承、未知字段、缺失文件、校验不一致、适配器单元名不匹配均阻止运行。

| files 角色 | 含义 |
|---|---|
| layout | 矩形文本版图 |
| params | 器件、材料、掺杂和网格参数 |
| stack | 层叠及物理层角色 |
| rules | 当前文本规则/层关系格式 |
| n_va / p_va | N/P Verilog-A 模型 |
| pin | R/C/FET/PORT 清单 |
| bench | 电源、负载、激励和判定阈值 |
| adapter | 该单元的生成/执行/分析脚本 |
| r_matrix / c_matrix | 与节点清单匹配的 R/C 矩阵 |

`stages` 为 `sde`、`drc`、`pex` 的非空不重复列表，执行顺序固定为 SDE → DRC → PEX。几何阶段要求 layout/params/stack/rules；PEX 要求另外七项输入。只具有电路连接和矩阵的配置使用 `["pex"]`，不能借用其他单元的几何文件冒充完整流程。

`options` 支持 `md_layer`、`bmd_layer`、`backside_prefix` 和布尔值 `strict_contact_face`。`warnings` 保存已知限制；`provenance` 保存模型、矩阵来源。修改矩阵后须重新核对 pin 节点，修改单元拓扑时须同步修改 pin、bench、adapter、矩阵和几何；文件齐全与哈希一致只是输入完整性检查。

原 `test copy` 的 `.drc`、旧 pin 格式及不完整模板保留在历史归档和输入清单中，不直接登记为可执行的新格式配置。转换必须有对应格式和语义验证。

当前本地包：

| 包 | 范围与已知限制 |
|---|---|
| inv_reference | INV，全生成链路，人工 RC |
| sram_reference | SRAM，全生成链路，历史矩阵来源待核对 |
| nand2_backend | NAND2 后级电路，人工 RC；不启用遗留 INV 几何 |
| nor2_backend | 10 器件等效 NOR2 后级，人工 RC；保留原数值告警策略 |

每次运行在外部数据目录建立新的编号，复制输入和框架，保存 `manifest.json`。生成状态为 `generated`，调度检查为 `dry_run_completed`；执行器返回成功并不自动认定科学结果合格。解析输出保存原始状态和告警，历史汇总不会转换成虚假的“已重跑通过”。
