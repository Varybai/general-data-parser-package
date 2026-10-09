# 设计来源与现有实现映射

设计输入：

- [CAD Document Ingest Baseline 0.1.0](https://github.com/yijunw-aiVersion/cad-document-ingest/tree/192f2c9dd10a283eef3a4112b4e87de2a12073b9)：事实/观察/假设、profile、文档投影和本地/远端门槛。
- [Uni-Viking LDraw 视觉分支](https://github.com/Varybai/Uni-Viking/tree/cefd7e97773a5c3484206ec99040c6ea74361150)：真实源闭包、实际渲染与模型输入、哈希缓存、隐藏来源同步和恢复。

| 原设计 | 本包的通用化 |
|---|---|
| LDraw/Shadow 数据 | 格式适配器的源声明、提取和计算事实 |
| 单张 PNG | 按任务选择图像、页面、音视频或其他证据，允许不适用 |
| purpose_candidate | hypotheses；未知可为 null，用途始终未验证 |
| part/model/connector 文档 | 三类解析文本；独立摘要按需启用 |
| OpenViking 原生解析与摘要 | 已支持的输入直接交给后端，Skill 编排与验收 |
| 原生源版本 | 源、配置、观察与规定正文的完整交付版本 |

## LDraw 适配建议

若当前 OV 已启用 LDraw 原生解析，直接提交原始 .dat/.ldr/.mpd 并回读；不在 Agent 端重复搭建解析链。需要独立本地输出或明确补充时，使用现有原生解析结果、part/model 文档、`.source/manifest.json` 和 compiled-connectors 作为事实；使用真实几何闭包渲染图作为观察证据。映射字段时保留原产物。

model_generated 保留模型来源；真实看图证据充分时可记录 reviewed，随后仍需一致性检查。partial 必须满足必要字段/覆盖门槛。OV 的 L0/L1 由语义处理流程生成，适配时使用 backend 摘要模式并核对数字、来源和边界；custom 正文关系只适用于用户要求的独立 local 摘要。

本包没有携带 LDraw 后端，也不把列举的格式当成已验证能力。安装 Skill 不安装解析库、CAD 工具、模型或知识库服务。

## 0.2.0 可执行工程适配

新增标准库格式解析代码、源重放校验及统一 E01–E09 门槛。保留来源/观察/推断分工，并要求新格式提供真实代码与独立正反样本。已有 OV 文档能力继续复用；工程结构化提取不以单纯的扩展名支持代替实际能力。
