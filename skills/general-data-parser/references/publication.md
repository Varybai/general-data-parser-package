# 后端解析、发布与恢复

## 原文件直入（parse_owner=backend）

1. 确认目标服务已启用并能满足该输入的解析需求。PDF、Office 等由 OV 已配置的路由处理；不要只凭后缀或源码中的支持列表声称当前服务可用。
2. 保存原件/依赖的实际字节、哈希和路由依据。profile 设置 parse_owner=backend、backend=openviking、summary_owner=backend、roles={}。审计侧保留 manifest/receipts/acceptance，不强制生成本地 facts/observations/asset。
3. 通过当前公开工具上传或提交原文件，沿用原始文件名/扩展名与用户指定元数据。上传若已经启动摄取，保存返回的任务 ID 并跟踪，不重复发起第二次入库。审计侧配置与报告不整包上传成业务内容。
4. 等待实际解析、语义与索引任务，记录输入哈希、任务、资源 URI、解析路由、来源字段、诊断和原生正文。后端已有源码映射/原始附件直接复用；没有的字段标未知，必要缺口单独报告。
5. 回读后端正文并抽样对照原文，检查覆盖、关键内容、来源、L0/L1、索引与目标检索。可以为验收查看原页面或抽取个别字段；这不是另一条全量入库内容生产路径。

required_checks 为 input.integrity 和 backend.capability。publication_checks 至少包含 remote.parse、content.fidelity、content.coverage、document.consistency、remote.bytes、remote.index、remote.query，以及 OV 的 remote.summaries。必要感知检查在后端结果产生后执行。

后端会转换源内容。remote.bytes 对比实际保留的原件或已回读产物的对应哈希，不能要求转换后的 Markdown 等于原 PDF 字节。若原件不能远端回读，保留本地源与上传回执并说明边界；用户要求的原件回读门槛不能假填通过。

## 本地或额外提取后发布（parse_owner=local）

只有独立交付、已确认的后端能力缺口或明确的额外提取需求才安排本地处理。先复用后端已有正文与证据，再对限定字段/页面/对象补充；不默认重复解析整份 PDF/Office。

完成本地内容验收后，通过明确的 URI/schema 映射发布派生文档，保留与原件/原资源的链接和处理原因。不要把同一份源内容作为独立资源重复入库。OV 仍管理 L0/L1。

## 版本与恢复

目标不存在则创建，相同内容按幂等策略复用，同身份同版本发生内容冲突时停止冲突范围写入。使用条件写入、幂等键或单写入者，保留边界。响应不明时先回读实际副作用，再恢复缺失部分；一次网络失败不直接改用另一套解析器重发。

后端正文、摘要与来源目录沿用其公开接口和原生组织。只读验证不修复。发现漂移时标 invalidated，按已授权范围修正并重新验收。不要复制 asset 覆盖 OV 摘要，也不要为统一文件名直接修改后端内部存储。

backend 模式的 ready_to_submit 只证明输入与能力检查；本地 local_ready 只证明本地解析；published 要求本次解析、内容、摘要、索引和检索全部通过。部分完成与未知结果分别记录。

同步/恢复时保留隐藏来源、输入/目标哈希和检查点；锁必须覆盖实际读写移动路径。缓存复用核查源、工具/配置、profile、模型/提示词和输出哈希，不能把旧成功记录当成新版本通过。
