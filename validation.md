# 0.1.2 后端优先解析验证

日期：2026-10-09。增加 parse_owner=backend/local。后端已支持的格式直接提交原文件，Skill 编排与验收；本地解析只用于独立交付或明确缺口。

- 45 项回归通过，新增 10 项覆盖无本地解析文档的后端输入包、能力失败、待解析任务、正文与覆盖门槛、错误预解析、本地额外提取原因和完成状态。
- 后端模式以 ready_to_submit 表示输入就绪，只有真实后端解析/内容/摘要/索引/检索验收通过才能 published。
- 本轮只读核对 Uni-Viking 4d394a0 的 PDFParser、AnyDocParser 和 ParserRouter；当前部署是否启用相应路由仍需运行环境证据。未调用线上 PDF/Office 解析或模型。
- 后端相关回归使用模拟回执，验证契约与门槛；不证明生产解析质量。历史安装和样本记录保留在下方。

---

# 0.1.1 摘要职责修正验证

日期：2026-10-09。新增 summary_owner=none/local/backend；OV 使用 backend，L0/L1 由 OV 自动生成，Skill 回读与验收。

- 35 项回归通过；其中 10 项覆盖三类/五类产物、OV 摘要归属、发布阶段门槛、旧版兼容及待生成摘要。
- OV 模式本地就绪不依赖后端摘要；published 必须有通过的 remote.summaries 检查。
- 后端相关新测试使用模拟回执，只验证契约和状态规则；本轮未调用线上 OV 或模型。
- 0.1.0 的源快照和安装验收保留在下方历史记录及对应 JSON 中。

---

# 本轮验证记录

日期：2026-10-09。验证对象：General Data Parser 0.1.0。

## 已执行

| 检查 | 结果 |
|---|---|
| Skill Creator quick_validate | 通过，Skill is valid |
| 包内文件、相对引用、Markdown fence、JSON 模板 | 通过：10 个 Skill 文件、9 个资源引用、5 个 JSON 模板 |
| 只读验收器回归 | 25 项通过 |
| Python 基础静态检查 | Ruff E9/F 通过 |
| ZIP 解压与独立运行 | 10 个文件逐字节一致；从隔离解压目录执行验收器，三个样本均通过；解压后的 Skill Creator 校验通过 |
| CSV 真实小样本 | 3 行；引号内逗号、0、空字符串与数量和正确保留；文档回读一致 |
| JSON 真实小样本 | 嵌套结构、null、0、空数组、中文及大整数 9007199254740993 正确保留 |
| Markdown 真实小样本 | UTF-8、空行、数量与否定句正确保留；文档回读一致 |

回归覆盖来源篡改、profile/对象错版、正文漂移、必需检查失败、未执行却填 pass、缺回执、必需观察未完成、观察矛盾、unknown 填 0、partial 无披露、发布缺门槛、路径跳转、符号链接、未列文件、重复 JSON 键、NaN/溢出数值和角色文件映射。

小样本产物及实际核对回执在 [validation/smoke/](validation/smoke/)，汇总见 [summary.json](validation/smoke/summary.json)。测试使用独立预期值和文档 JSON 回读比较；验收器只负责契约与绑定核对。

分发包解压校验和从解压目录运行的结果另见 `validation/distribution.json`。

## 验证边界

本轮真正转换的是自建 CSV、JSON、Markdown 小样本。PDF、办公文件、图片、音视频、CAD 和数据库等只提供适配 SOP 与验收要求，没有在本轮执行其解析后端。

观察相关单元测试使用明确标记的模拟回执，仅验证状态和绑定规则。本轮没有真实视觉/语音模型调用，也没有远端发布。Skill 不携带通用解析后端，无法仅凭安装宣称支持所有列举格式。

本轮由主会话直接实现和验证；未执行独立 Agent 行为评估。脚本通过不能证明未来 Agent 一定遵守所有规则，也不替代领域内容验收。

## Pi package 与标准 Skills CLI 本地验证

- Pi 1.0.4：在隔离项目执行本地 package 安装，真实资源加载器发现 general-data-parser，零相关诊断，已进入 Skill 提示清单。
- Skills CLI 1.5.25：发现并复制 1 个 Skill 到 Pi 项目目录，10 个文件逐字节一致，安装后的验收器成功检查 CSV 样本。
- npm 12.0.2：dry-run 包含 package.json、README.md 和 10 个 Skill 文件，共 12 个；没有根目录运行依赖。打包检查兼容 npm 11 的数组输出和 npm 12 的对象输出。
- Node.js 24.19.0；上述安装使用隔离 Pi 配置和 Skills 状态目录。

结构化证据：[install-local.json](validation/install-local.json)。

## GitHub 远端安装验证

公开仓库：<https://github.com/Varybai/general-data-parser-package>。

- 在新的隔离项目执行 pi install git:github.com/Varybai/general-data-parser-package --local --approve：安装成功；Pi 1.0.4 资源加载器发现 1 个目标 Skill，零相关诊断，进入提示清单。
- 执行 npx --yes skills add Varybai/general-data-parser-package --skill general-data-parser --agent pi --copy --yes：Skills CLI 1.7.1 安装成功；Pi 同样能够发现安装结果。
- 两种安装结果各有 10 个 Skill 文件，均与源文件逐字节一致；各自安装目录中的验收器均成功检查 JSON 样本。
- 首次发布提交 e4c7360 的 GitHub Actions 已通过包结构、25 项回归、三个样本转换和 npm 文件清单检查。

结构化证据：[install-remote.json](validation/install-remote.json)。安装验收覆盖该记录中的源提交与 Skill 内容哈希；本次后续提交仅增加验收记录。
