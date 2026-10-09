# General Data Parser Package

一个仓库同时提供 **Pi coding agent package** 和标准 **Agent Skill**。两种安装方式使用同一份 `skills/general-data-parser/`。

0.2.0 增加可执行的工程数据解析器及源重放验收。统一验收标准约束所有格式；适配器负责实际代码解析和专项检查。OV 已满足任务的文档解析能力继续复用。

## 0.2.0 可执行工程解析

首批内置 CSV/TSV（含可选时序）、JSON/JSONL、XML、STL（ASCII/二进制）和 OBJ 的明确子集，使用 Python 3.10+ 标准库。它们实际生成完整结构、源定位、指标、事实、说明和回执，并执行专项检查。

从 Skill 目录运行，或使用安装后的脚本完整路径：

~~~bash
python3 scripts/parse_file.py --list-formats
python3 scripts/parse_file.py ./signals.csv --time-column time --time-unit ms --output ./out/signals-v1
python3 scripts/parse_file.py ./part.stl --length-unit mm --require-unit --output ./out/part-v1
python3 scripts/verify_engineering.py ./out/part-v1 --require-ready
~~~

| 交付 | 作用 |
|---|---|
| source/ | 原始输入字节 |
| data/parsed.json | 完整结构化表示与来源定位 |
| facts.json / asset.md | 指标、事实与可读说明 |
| observations.json | 真实观察状态；代码不假填 reviewed |
| profile / manifest / receipts / acceptance | 规则、哈希、实际执行与验收结果 |

JSON 数字保留词法及类型映射，避免浮点精度损失。网格单位不猜测，时序起点/时区不假定。坏行、未知几何和资源上限不能静默丢弃。

统一标准见 [E01–E09](skills/general-data-parser/references/engineering-acceptance.md)；新增格式见 [代码适配接口](skills/general-data-parser/references/adapter-development.md)。STEP/IGES/DXF/IFC、HDF5/NetCDF/VTK 尚未内置，须实现并通过样本验收后才声明支持。

## 安装到 Pi

在目标项目目录执行：

```bash
pi install git:github.com/Varybai/general-data-parser-package --local
```

省略 `--local` 时安装到用户范围。Pi 首次加载项目资源时按其界面确认项目信任；已有会话使用 `/reload`。

调用：

```text
/skill:general-data-parser 解析这批文件，保留原始证据，按规定产物和验收标准逐对象交付。
```

Git 安装直接从此仓库读取 Pi manifest，无需发布到 npm。仓库的 `package.json` 使用：

```json
{
  "name": "general-data-parser-package",
  "keywords": ["pi-package", "agent-skills"],
  "files": ["skills/", "README.md"],
  "pi": {"skills": ["./skills"]}
}
```

## 使用标准 Skills CLI

交互选择目标 Agent：

```bash
npx skills add Varybai/general-data-parser-package
```

明确安装到 Pi 或 Codex：

```bash
npx skills add Varybai/general-data-parser-package --skill general-data-parser --agent pi --copy --yes
npx skills add Varybai/general-data-parser-package --skill general-data-parser --agent codex --copy --yes
```

两条命令是按目标选择的替代方案。Skills CLI 默认项目范围，`--global` 为用户范围；最终路径以实际 CLI 版本为准。在同一项目中为同一 Agent 选择一种安装方式，避免重复加载同名 Skill。

Codex 等支持美元符号调用的 Agent 使用 `$general-data-parser`。查看仓库可安装条目：

```bash
npx skills add Varybai/general-data-parser-package --list
```

## 内容与边界

| 内容 | 文件 |
|---|---|
| Agent 入口 | [SKILL.md](skills/general-data-parser/SKILL.md) |
| 解析 SOP | [sop.md](skills/general-data-parser/references/sop.md) |
| 九类数据格式适配 | [adapters.md](skills/general-data-parser/references/adapters.md) |
| 产物契约 | [output-contract.md](skills/general-data-parser/references/output-contract.md) |
| 验收标准 | [acceptance.md](skills/general-data-parser/references/acceptance.md) |
| 模板 | [templates.md](skills/general-data-parser/assets/templates.md) |
| 发布与失败恢复 | [publication.md](skills/general-data-parser/references/publication.md) |
| 设计来源 | [design-origin.md](skills/general-data-parser/references/design-origin.md) |

parse_owner=backend 时，原文件直接由 OV 等已配置的后端解析；Agent 记录输入哈希、路由、任务、资源 URI 和回读验收。无需先生成本地 facts/observations/asset。

需要工程结构化数据和数值/网格/时序检查时，使用代码适配器并按本地契约生成产物；已有后端结果满足需求时可复用。OV 目标下记录所需工程能力与处理原因。

| 摘要归属 | L0/L1 的生成者 |
|---|---|
| none（普通解析） | 不要求独立 L0/L1 |
| local（用户要求独立摘要） | Agent 在本地生成并验收 |
| backend（OV 入库） | OV 自动生成；Skill 等待、回读并验收 |

OV 模式不预写或覆盖 .abstract.md/.overview.md。后端直入的输入通过检查后标为 ready_to_submit，解析与回读完成才 published。独立本地解析则保留 local_ready 阶段。保留源声明、计算事实、感知观察和推断的区别。

Skill 现在包含标准库可执行适配器、产物完整性验收器和实际源重放检查器。更广的格式仍需真实库/API 实现；本包不自动安装 CAD 内核、科学数据依赖、模型或知识库服务。

verify_bundle 检查契约与字节；verify_engineering 实际重读源并比较完整表示、事实、说明和专项条件。重放不是独立算法正确性证明，需配合已知答案测试；感知、制造和物理性能仍需要相应验证。

## 维护与验证

以下命令在仓库 checkout 中执行：

```bash
npm test
python3 -B scripts/smoke_formats.py --output /path/to/new-isolated-output
python3 -B scripts/smoke_engineering.py --output /path/to/new-engineering-output
npm pack --dry-run --ignore-scripts
npm run pack:skill
```

`npm pack` 只包含共享 Skill、README 和 package manifest。测试、样本及维护脚本保留在 Git 仓库，不成为 npm 运行依赖。GitHub Actions 验证包结构、回归、原有小样本、八个工程输入的真实解析与重放，以及 npm 文件清单。

[验证记录](https://github.com/Varybai/general-data-parser-package/blob/main/validation.md)区分历史流程/安装验证与 0.2.0 可执行适配器的实际测试范围。新格式列表以已执行测试和声明子集为准。
