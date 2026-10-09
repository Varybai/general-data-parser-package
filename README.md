# General Data Parser Package

一个仓库同时提供 **Pi coding agent package** 和标准 **Agent Skill**。两种安装方式使用同一份 `skills/general-data-parser/`。

将异构数据解析组织为：确认后端能力、选择解析归属、保留原文件、执行现有解析路径、核验内容与证据。目标后端已支持的 PDF/Office 等直接提交原文件；额外适配只处理明确缺口或独立交付需求。

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

parse_owner=local 时，才按本地契约生成 facts、observations、asset，附源证据与回执。OV 目标下需记录本地处理的明确原因。

| 摘要归属 | L0/L1 的生成者 |
|---|---|
| none（普通解析） | 不要求独立 L0/L1 |
| local（用户要求独立摘要） | Agent 在本地生成并验收 |
| backend（OV 入库） | OV 自动生成；Skill 等待、回读并验收 |

OV 模式不预写或覆盖 .abstract.md/.overview.md。后端直入的输入通过检查后标为 ready_to_submit，解析与回读完成才 published。独立本地解析则保留 local_ready 阶段。保留源声明、计算事实、感知观察和推断的区别。

Skill 提供操作方法和 Python 3.10+ 标准库只读验收器。实际解析依赖 Agent 环境中的格式库、应用或模型；安装本包不会安装这些后端、模型凭据或知识库服务。格式示例不是已测试支持矩阵。

验收器检查文件、哈希、版本绑定、正文关系与报告门槛。关键字段、覆盖和感知内容需要真实核对；结构检查通过不等于语义准确。

## 维护与验证

以下命令在仓库 checkout 中执行：

```bash
npm test
python3 -B scripts/smoke_formats.py --output /path/to/new-isolated-output
npm pack --dry-run --ignore-scripts
npm run pack:skill
```

`npm pack` 只包含共享 Skill、README 和 package manifest。测试、样本及维护脚本保留在 Git 仓库，不成为 npm 运行依赖。GitHub Actions 验证包结构、验收器回归、小样本转换与 npm 文件清单。

[验证记录](https://github.com/Varybai/general-data-parser-package/blob/main/validation.md)区分历史安装/样本验证、0.1.1 的摘要归属修复与 0.1.2 的 45 项回归。基础转换样本为 CSV、JSON、Markdown；其他格式按实际后端验证。
