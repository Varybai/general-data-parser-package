# 解析产物契约

## 文件角色

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

默认解析文本为 facts、observations、asset 三类。只有用户要求本地摘要时，才增加 abstract、overview 两类。文件名由 profile.roles 映射；用户使用其他 schema 时记录映射与等价检查。

## 摘要归属

| summary_owner | 适用场景 | 本地产物和验收 |
|---|---|---|
| none | 普通解析，无独立分层摘要要求 | 三类文本；不要求 L0/L1 |
| local | 用户明确要求独立摘要文档 | 五类文本；本地生成并核对 L0/L1 |
| backend | OV 或其他自动摘要后端 | 三类本地文本；发布后回读后端的 L0/L1 |

新 profile 明确填写此字段，普通解析使用 none。OV 目标必须使用 backend，并填写 backend=openviking。0.1.0 的旧 profile 缺少此字段时，验收器按旧版 local 行为兼容；用于 OV 前必须迁移。

## profile

`schema_version=general-parser.profile.v1`。包含 id、output_language、format、adapter、roles、observation_policy、summary_owner、required_checks。backend 模式另填 backend 和 publication_checks；local 模式另填 overview_relation。adapter 记录实际工具/版本/选项/支持范围，可扩展渲染器、模型、提示词与模板版本；不写凭据。

observation_policy 为 required / optional / not_applicable。只有 local 模式允许 overview_relation，默认 identical，custom 时说明差异核验方法。backend/none 模式删除 overview_relation 和 overview_rule；不要求后端 L1 等于 asset。配置原字节 SHA-256 是 profile_sha256。

required_checks 是本地门槛，至少有 `content.fidelity`、`content.coverage`、`document.consistency`，按格式增加专项；required 观察另加 `observation.consistency`。publication_checks 是发布门槛，包含 `remote.bytes`、`remote.index`、`remote.query`；backend 摘要模式还必须有 `remote.summaries`。

本地就绪不等待发布门槛；只有声明 published 时，才要求两组检查均通过。发布检查可以暂不记录或记录为未执行，不能因此阻止合格的本地解析。旧 profile 将 remote 检查放在 required_checks 时仍按其旧约束执行。

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

asset 包含身份、任务相关事实、观察/假设、未知、覆盖、来源链接与边界。local 模式默认 overview 与 asset 字节相同，abstract 从同版内容摘要；custom 关系也须核查一致性。backend 模式由后端生成摘要，仅验收其存在、非占位内容、来源一致性与索引状态，不做本地字节等同要求。

包内相对链接必须可解析。展示可截断，但记录展示量/总量并链接完整数据。外部 URL 不能替代必需的源字节或本地证据。

## manifest 与哈希

`schema_version=general-parser.manifest.v1`，含 object_id、version、files。每项为 path、role、sha256、size_bytes。role 为 profile/source/dependency/facts/observations/asset/abstract/overview/evidence/receipt。profile、facts、observations、asset 各一个，source 至少一个；local 模式另有 abstract、overview 各一个。backend/none 模式不允许把后端受管摘要作为本地输出。回读结果保存为 receipts 内的独立记录，不能回灌到受管摘要路径。

清单覆盖目录全部文件，**除 manifest.json 与 acceptance.json**，避免哈希递归。路径为 POSIX 相对路径，禁止绝对路径、跳转、符号链接和重复。逐文件 hash/size 针对实际字节。

source_manifest_sha256：选 source/dependency 项，只保留 path、role、sha256；按 path 排序，以 `ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False` 序列化为无末尾换行的 UTF-8 JSON，计算 SHA-256。

## acceptance

`schema_version=general-parser.acceptance.v1`。含 object_id、version、manifest_sha256、profile_sha256、source_manifest_sha256、state、checks、limitations。

check 含唯一 id、executed、result、method、evidence（清单内回执路径列表）、reason。result 为 pass/fail/unknown/skipped/unsupported；pass 需 executed=true、非空方法和证据。profile.required_checks 每项均有记录；published 状态还要求 publication_checks 的记录和结果。remote.summaries 的回执记录实际目标 URI、读取时间、资源版本、L0/L1 原始响应或正文与哈希、内容和占位检查。该回执仅证明记录的检查，不由本地验证器代替远端读取。

报告本身不进入 manifest；归档时可在包外索引保存报告哈希。修正导致字节变化时重建清单并重跑受影响检查。脚本核对格式与字节；字段含义、定位准确性和内容覆盖由实际格式核验承担。
