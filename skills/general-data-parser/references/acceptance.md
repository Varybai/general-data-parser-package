# 解析后文件验收标准

## 按解析归属执行

后端模式提交前只验证 input.integrity（实际源字节、对象与版本）和 backend.capability（当前服务路由、依赖与任务支持范围），不要求本地解析文档。ready_to_submit 只表示可以提交。

提交后验证 remote.parse：实际任务完成、输入与结果绑定、真实解析路由及错误/损失。再对后端结果执行下表的内容、覆盖、摘要、索引和检索检查。回读不能只检查摘要而漏掉解析正文。

## 通用门槛

| 检查 | 通过标准 | 实际方法 |
|---|---|---|
| 身份与版本 | 产物属于同一对象、源快照和 profile | 重算绑定哈希、核对身份 |
| 输入与工具 | 原始字节、实际依赖、工具版本/参数和损失可追溯 | 输入清点、hash、实际执行回执 |
| content.fidelity | 用户要求的关键字段与源/API/独立计算一致 | 定位原文、记录预期/实际值和方法 |
| content.coverage | 页/行/记录/对象/时间段覆盖满足范围 | 总量、处理量、遗漏、抽样方法 |
| observation.consistency | required 时实际读取且内容不与可核验事实矛盾 | 证据读取回执、图像/片段与事实交叉核对 |
| document.consistency | 正文数字/关系/单位/否定/未知与事实和观察一致 | 检查解析正文与链接；仅 local 模式默认 asset/L1 同字节 |
| 文件完整性 | 后端模式的源与回执，或本地模式要求的文本及证据完整，格式/哈希/路径正确 | verify_bundle.py |
| 远端交付 | 本次要求的字节、索引、查询与来源回读通过 | remote 检查与真实远端回执 |
| remote.summaries | backend 模式的后端 L0/L1 已生成、可回读、非占位且与本次来源一致 | 保存实际 URI、时间、版本、正文与哈希，检查关键事实/边界及检索 |

关键字段至少包含身份和用户关心的信息。覆盖必须有任务分母。模型在同一次生成中自称正确不是独立核验；使用源定位、其他计算路径或实际审阅。源不提供现实真值时，只能报告“与源一致”。质量阈值按任务约定，不虚构通用正确率。

## 状态

| 状态 | 条件 |
|---|---|
| prepared | 已准备输入或部分产物，必要检查尚未完成 |
| ready_to_submit | 后端模式的输入/能力检查通过；解析尚未完成 |
| visual_review_required | 必需感知审阅未完成，也适用于音频等 |
| local_ready | 通用与格式必需项实际通过，无未披露可选缺口 |
| local_ready_with_limitations | 必需项通过，可选缺口已披露 |
| published | 本地与本次远端门槛通过 |
| failed / unsupported / conflict | 检查失败 / 能力不足 / 同版不同内容 |
| remote_unknown / remote_incomplete | 写入结果未知 / 发布部分完成 |
| invalidated | 旧检查因输入、配置、正文或远端变化失效 |

本地 required_checks 的 fail/unknown/skipped/unsupported 阻止本地就绪。publication_checks 只在发布完成时成为必需门槛。后端接管解析时，提交前报告 ready_to_submit，之后报告真实任务状态；摘要尚未完成不能 published。本地解析完成后再发布的模式可以保留 local_ready。partial 必须证明遗漏只影响约定可选范围，否则不通过。降级不得掩盖用户要求的失败项。

## 执行

本地模式先核对事实、覆盖和观察，再生成核对正文；后端模式先准备原文件，再对后端输出核对这些项；生成 manifest 后把其哈希写入报告。在 Skill 目录运行：

```bash
python3 scripts/verify_bundle.py /path/to/bundle --require-ready
```

省略 --require-ready 可检查 prepared 或 ready_to_submit 的输入包；后端模式带该参数时必须达到 published。输出分别记录 structural_validation 和 recorded_required_checks_passed。脚本不证明回执动作真实发生，也不自行判定语义准确性。无 Python 时执行等价检查并记录实际方法，不声称运行了脚本。

## 应覆盖的失败案例

| 情形 | 预期结果 |
|---|---|
| 同名源字节不同、配置或图像改变 | 旧观察/检查失效，新快照或版本 |
| 缺依赖、缺页、坏行、漏段 | 覆盖不足，必要门槛失败 |
| 空值变 0、重复键丢失、未知单位被猜测 | 事实检查失败 |
| 有图片却未看图 | not_run，required 时等待审阅 |
| 正交对象被描述为平行 | 观察一致性失败，修正观察或保留失败 |
| 摘要数字/否定与源不同 | 文档一致性失败 |
| 同版正文或图片改变 | 发布冲突 |
| 上传成功但查询不到、后端摘要未生成或回读不同 | 本地状态保留；不能 published |
| 后端已支持文档却要求本地 facts/asset 才能提交 | 职责错误；直接提交原文件 |
| 原文件上传成功但解析任务仍排队/失败 | 不能 published |
| OV 输入包预先放入 .abstract.md/.overview.md | 摘要职责冲突；停止发布到受管路径 |
| 一批中某对象失败 | 逐对象状态；不得整批标记通过 |

本表是验收规范，只有实际执行后才能记录为本次证据。
