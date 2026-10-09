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
  .abstract.md
  .overview.md
  manifest.json
  acceptance.json
```

五类文本是 facts、observations、asset、abstract、overview。文件名由 profile.roles 映射；默认验证器要求保留下列信封语义。用户使用其他 schema 时记录映射并提供等价检查，不宣称未验证的兼容。

## profile

`schema_version=general-parser.profile.v1`。包含 id、output_language、format、adapter、roles、observation_policy、overview_relation、required_checks。adapter 记录实际工具/版本/选项/支持范围，可扩展渲染器、模型、提示词与模板版本；不写凭据。

observation_policy 为 required / optional / not_applicable。overview_relation 默认 identical，custom 时说明用户规则及差异核验方法。配置保存后的原字节 SHA-256 是 profile_sha256。

required_checks 至少有 `content.fidelity`、`content.coverage`、`document.consistency`，并添加格式专项。观察 required 时加入 `observation.consistency`；发布时加入 `remote.bytes`、`remote.index`、`remote.query`。

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

asset 包含身份、任务相关事实、观察/假设、未知、覆盖、来源链接与边界。默认 overview 与 asset 字节相同；abstract 从同版内容摘要，保留数值、单位、否定和未知。custom 关系也必须核查正文一致性。

包内相对链接必须可解析。展示可截断，但记录展示量/总量并链接完整数据。外部 URL 不能替代必需的源字节或本地证据。

## manifest 与哈希

`schema_version=general-parser.manifest.v1`，含 object_id、version、files。每项为 path、role、sha256、size_bytes。role 为 profile/source/dependency/facts/observations/asset/abstract/overview/evidence/receipt。profile 和五类文本各一个，source 至少一个。

清单覆盖目录全部文件，**除 manifest.json 与 acceptance.json**，避免哈希递归。路径为 POSIX 相对路径，禁止绝对路径、跳转、符号链接和重复。逐文件 hash/size 针对实际字节。

source_manifest_sha256：选 source/dependency 项，只保留 path、role、sha256；按 path 排序，以 `ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False` 序列化为无末尾换行的 UTF-8 JSON，计算 SHA-256。

## acceptance

`schema_version=general-parser.acceptance.v1`。含 object_id、version、manifest_sha256、profile_sha256、source_manifest_sha256、state、checks、limitations。

check 含唯一 id、executed、result、method、evidence（清单内回执路径列表）、reason。result 为 pass/fail/unknown/skipped/unsupported；pass 需 executed=true、非空方法和证据。profile.required_checks 每项均有记录。

报告本身不进入 manifest；归档时可在包外索引保存报告哈希。修正导致字节变化时重建清单并重跑受影响检查。脚本核对格式与字节；字段含义、定位准确性和内容覆盖由实际格式核验承担。
