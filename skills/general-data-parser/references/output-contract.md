# 解析产物契约

## 解析归属

profile.parse_owner 为 backend 或 local。新 profile 必须明确选择；旧 profile 缺字段时保留 local 行为。

- backend：原文件交给现有后端。审计目录只需 profile、source/依赖、receipts/必要回读证据、manifest、acceptance；roles={}。不要求本地 facts、observations、asset、L0/L1。它不是待整目录上传的业务资料包。
- local：独立本地交付或限定额外提取。使用下列内容契约。目标为 OV 时，明确填写 local_parse_reason，说明已确认的能力缺口或用户要求。

后端原生正文和来源文件保持其已有组织；Agent 记录 URI、任务、输入哈希及回读证据。只有用户需要额外结构化字段时才生成补充文档。

## 本地解析的文件角色

```text
object/version/
  profile.json
  source/                 # 原始字节、原扩展名及依赖
  evidence/               # 按需生成的预览、片段、转录
  receipts/               # 实际执行与内容核验回执
  facts.json
  observations.json
  asset.md
  .abstract.md            # 仅 summary_owner=local 时生成
  .overview.md            # 仅 summary_owner=local 时生成
  manifest.json
  acceptance.json
```

parse_owner=local 的默认解析文本为 facts、observations、asset 三类。只有用户要求本地摘要时，才增加 abstract、overview 两类。文件名由 profile.roles 映射；用户使用其他 schema 时记录映射与等价检查。

## 摘要归属

| summary_owner | 适用场景 | 本地产物和验收 |
|---|---|---|
| none | 普通解析，无独立分层摘要要求 | 三类文本；不要求 L0/L1 |
| local | 用户明确要求独立摘要文档 | 五类文本；本地生成并核对 L0/L1 |
| backend | OV 或其他自动摘要后端 | 回读后端 L0/L1；仅本地解析模式需要三类本地文本 |

新 profile 明确填写此字段，普通解析使用 none。OV 目标必须使用 backend，并填写 backend=openviking。0.1.0 的旧 profile 缺少此字段时，验收器按旧版 local 行为兼容；用于 OV 前必须迁移。

## profile

`schema_version=general-parser.profile.v1`。包含 id、output_language、format、adapter、parse_owner、roles、observation_policy、summary_owner、required_checks。后端接管解析时 adapter 标明所用服务/路由，未知版本明确记录而不伪造。后端接管解析或摘要时填写 backend 和 publication_checks；仅 summary_owner=local 填写 overview_relation。adapter 记录实际工具/版本/选项/支持范围，可扩展渲染器、模型、提示词与模板版本；不写凭据。

observation_policy 为 required / optional / not_applicable。只有 summary_owner=local 允许 overview_relation，默认 identical，custom 时说明差异核验方法。summary_owner=backend/none 删除 overview_relation 和 overview_rule；不要求后端 L1 等于 asset。配置原字节 SHA-256 是 profile_sha256。

parse_owner=local 时，required_checks 是本地门槛，至少有 `content.fidelity`、`content.coverage`、`document.consistency`，按格式增加专项；required 观察另加 `observation.consistency`。publication_checks 是发布门槛，包含 `remote.bytes`、`remote.index`、`remote.query`；backend 摘要模式还必须有 `remote.summaries`。

parse_owner=backend 时，required_checks 至少为 input.integrity、backend.capability。publication_checks 需要 remote.parse、content.fidelity、content.coverage、document.consistency、remote.bytes、remote.index、remote.query；OV 另有 remote.summaries，required 观察另有 observation.consistency。内容质量检查在后端产生结果后执行，不能要求提交前就完成。

后端输入就绪使用 ready_to_submit；不能用 local_ready 冒充完成本地解析。--require-ready 对后端模式只接受 published。

本地解析模式就绪不等待发布门槛；只有声明 published 时，才要求两组检查均通过。发布检查可以暂不记录或记录为未执行，不能因此阻止合格的本地解析。旧 profile 将 remote 检查放在 required_checks 时仍按其旧约束执行。

## 可执行工程产物

parse_file.py 在本地契约中增加 data/parsed.json（evidence 角色）与 receipts/parse.json、receipts/checks.json。data 采用 general-parser.data.v1，保存格式相关的完整结构和指标；大型数据不必复制进每条 facts。行/节点/面等定位在完整表示中，汇总指标关联全源范围和算法。

profile.adapter 记录实际适配器版本、Python 版本、代码哈希、声明范围和所有选项。缺单位、未解释材质、未观察等按任务必要性判定；不能把未知写成 0 或任意默认值。

verify_engineering 要求当前代码哈希与 profile 一致。规则变化后重新解析/验收并使用新版本目录。JSON 数字采用原始词法字符串加 numeric_tokens 类型映射，保留精度和数字/字符串区别；引用结果时必须同时读取映射。

## facts

`schema_version=general-parser.facts.v1`。含 object_id、version、profile_sha256、source_manifest_sha256、extraction、claims、diagnostics、limitations。

extraction 含 status（succeeded / partial / failed / unsupported）、tool、tool_version、receipt、losses。receipt 必须在文件清单内。

claims 各项含唯一 id、kind、status、value、unit、basis、reason。kind 为 source_declared / extracted / computed。status 为 known / unknown / partial / unsupported / not_applicable。known/partial 有 basis；partial 说明范围。其他状态的 value 为 null 并写原因。known 空值/空集合必须有源证据和完整性依据。

basis 是列表，每项至少为 `{path, locator, method}`。path 指向清单中的源、依赖、证据或回执；locator 是可重放定位的非空对象；method 说明提取/计算方法。未知数不用 0 代替；数值必须有限；高精度十进制可用字符串加类型说明。

## observations

`schema_version=general-parser.observations.v1`，含与 facts 相同身份及两个绑定哈希，另含 review_status、observer、observed_at、items、hypotheses、reason。

review_status 为 reviewed / not_run / skipped / failed。reviewed 需 observer（kind、id、receipt）、带时区时间和非空 items。observer.kind 为 model / agent / human。items 含唯一 id、kind（visual/audio/layout/semantic）、text、basis、limitations。basis 定位实际读取的证据。

hypotheses 含 id、text、status、based_on、reason。status 为 unverified / unknown / not_applicable；based_on 引用 claim/observation ID。没有合理推断时 text 为 null，写明原因。

未审阅状态必须有原因，items 为空；not_applicable 使用 skipped。reviewed 证明读取动作，准确性由 observation.consistency 检查；模型来源不能改写成人工确认。

## Markdown

asset 包含身份、任务相关事实、观察/假设、未知、覆盖、来源链接与边界。summary_owner=local 时默认 overview 与 asset 字节相同，abstract 从同版内容摘要；custom 关系也须核查一致性。summary_owner=backend 时由后端生成摘要，仅验收其存在、非占位内容、来源一致性与索引状态，不做本地字节等同要求。

包内相对链接必须可解析。展示可截断，但记录展示量/总量并链接完整数据。外部 URL 不能替代必需的源字节或本地证据。

## manifest 与哈希

`schema_version=general-parser.manifest.v1`，含 object_id、version、files。每项为 path、role、sha256、size_bytes。role 为 profile/source/dependency/facts/observations/asset/abstract/overview/evidence/receipt。profile 和 source 在两种解析模式都必需。后端模式只允许源、依赖、证据与回执角色；本地模式 facts、observations、asset 各一个；summary_owner=local 时另有 abstract、overview 各一个；summary_owner=backend/none 不允许把后端受管摘要作为本地输出。回读结果保存为 receipts 内的独立记录，不能回灌到受管摘要路径。

清单覆盖目录全部文件，**除 manifest.json 与 acceptance.json**，避免哈希递归。路径为 POSIX 相对路径，禁止绝对路径、跳转、符号链接和重复。逐文件 hash/size 针对实际字节。

source_manifest_sha256：选 source/dependency 项，只保留 path、role、sha256；按 path 排序，以 `ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False` 序列化为无末尾换行的 UTF-8 JSON，计算 SHA-256。

## acceptance

`schema_version=general-parser.acceptance.v1`。含 object_id、version、manifest_sha256、profile_sha256、source_manifest_sha256、state、checks、limitations。

check 含唯一 id、executed、result、method、evidence（清单内回执路径列表）、reason。result 为 pass/fail/unknown/skipped/unsupported；pass 需 executed=true、非空方法和证据。profile.required_checks 每项均有记录；后端模式的这组检查仅表示输入和可用能力。published 状态还要求 publication_checks 的记录和结果。remote.summaries 的回执记录实际目标 URI、读取时间、资源版本、L0/L1 原始响应或正文与哈希、内容和占位检查。该回执仅证明记录的检查，不由本地验证器代替远端读取。

报告本身不进入 manifest；归档时可在包外索引保存报告哈希。修正导致字节变化时重建清单并重跑受影响检查。脚本核对格式与字节；字段含义、定位准确性和内容覆盖由实际格式核验承担。
