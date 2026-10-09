# 产物模板

先按 parse_owner 选择模板，只使用对应分支。后端直入不创建本地解析三件套。复制到对象版本目录并填入真实执行值。`REPLACE_*` 是待替换项，不是可交付内容。先固定 profile 和源，再计算绑定哈希；清单覆盖全部实际文件，最后写报告。模板本身不证明执行或通过。

## OV 原文件直入：profile.json

先确认当前 OV 路由满足任务。此模式只提交原文件；以下 profile 和回执保留在审计侧。observation_policy 按任务选择；required 时把 observation.consistency 加入 publication_checks。

```json
{
  "schema_version": "general-parser.profile.v1",
  "id": "REPLACE_PROFILE_ID",
  "format": "REPLACE_DETECTED_FORMAT",
  "output_language": "zh",
  "parse_owner": "backend",
  "backend": "openviking",
  "adapter": {"tool": "REPLACE_ACTUAL_OV_ROUTE", "version": "REPLACE_OBSERVED_VERSION_OR_UNREPORTED"},
  "roles": {},
  "summary_owner": "backend",
  "observation_policy": "REPLACE_POLICY",
  "required_checks": ["input.integrity", "backend.capability"],
  "publication_checks": ["remote.parse", "content.fidelity", "content.coverage", "document.consistency", "remote.bytes", "remote.index", "remote.query", "remote.summaries"]
}
```

## OV 原文件直入：acceptance.json

预检完成后才可设 ready_to_submit；实际解析、内容及远端检查全部通过后才能设 published。解析正文和来源保持 OV 原生组织，通过回执记录 URI、任务、哈希和核验，不重建 facts/asset。

```json
{
  "schema_version": "general-parser.acceptance.v1",
  "object_id": "REPLACE_OBJECT_ID",
  "version": "REPLACE_OBJECT_VERSION",
  "manifest_sha256": "REPLACE_MANIFEST_BYTES_SHA256",
  "profile_sha256": "REPLACE_PROFILE_BYTES_SHA256",
  "source_manifest_sha256": "REPLACE_SOURCE_MANIFEST_SHA256",
  "state": "prepared",
  "checks": [
    {"id": "input.integrity", "executed": false, "result": "unknown", "method": null, "evidence": [], "reason": "尚未核对输入"},
    {"id": "backend.capability", "executed": false, "result": "unknown", "method": null, "evidence": [], "reason": "尚未确认当前后端能力"}
  ],
  "limitations": []
}
```

manifest 使用下方通用模板；后端模式枚举原文件、依赖、profile 和真实回执，不枚举本地 facts/observations/asset。

## 独立或额外提取：profile.json

```json
{
  "schema_version": "general-parser.profile.v1",
  "id": "REPLACE_PROFILE_ID",
  "format": "REPLACE_DETECTED_FORMAT",
  "output_language": "zh",
  "parse_owner": "local",
  "adapter": {
    "tool": "REPLACE_ACTUAL_TOOL",
    "version": "REPLACE_ACTUAL_VERSION",
    "options": {},
    "supported_scope": [],
    "required_fields": []
  },
  "roles": {
    "facts": "facts.json",
    "observations": "observations.json",
    "asset": "asset.md"
  },
  "observation_policy": "REPLACE_POLICY",
  "summary_owner": "none",
  "publication_checks": [],
  "required_checks": ["content.fidelity", "content.coverage", "document.consistency"]
}
```

把本次格式专项加入 required_checks；required 观察增加 observation.consistency。发布检查单独放入 publication_checks，至少有 remote.bytes、remote.index、remote.query。

如果仅把独立解析结果发布给 OV，可设 summary_owner=backend，并写入 backend=openviking 与明确的 local_parse_reason，再增加发布检查。普通 OV 已支持格式直接使用上方原文件直入模板，不套用此本地模板。只有用户要求独立本地摘要时才改为 local，在 roles 增加 abstract/overview 两项，并设置 overview_relation=identical。根据源记录单位、坐标、时区、编码及实际依赖，不擅设未知单位。

## facts.json

```json
{
  "schema_version": "general-parser.facts.v1",
  "object_id": "REPLACE_OBJECT_ID",
  "version": "REPLACE_OBJECT_VERSION",
  "profile_sha256": "REPLACE_PROFILE_BYTES_SHA256",
  "source_manifest_sha256": "REPLACE_SOURCE_MANIFEST_SHA256",
  "extraction": {
    "status": "REPLACE_EXECUTED_STATUS",
    "tool": "REPLACE_ACTUAL_TOOL",
    "tool_version": "REPLACE_ACTUAL_VERSION",
    "receipt": "receipts/parse.json",
    "losses": []
  },
  "claims": [{
    "id": "REPLACE_FIELD_ID",
    "kind": "source_declared",
    "status": "unknown",
    "value": null,
    "unit": null,
    "basis": [],
    "reason": "尚未获得此字段；解析后填写实际值或保留未知原因"
  }],
  "diagnostics": [],
  "limitations": []
}
```

known/partial 字段的 basis 使用 `{ "path": "source/input.csv", "locator": {"row": 2, "column": "amount", "row_base": 1}, "method": "实际方法" }` 这样的结构。不同格式使用对应定位；计算值还应链接计算回执。

## observations.json

```json
{
  "schema_version": "general-parser.observations.v1",
  "object_id": "REPLACE_OBJECT_ID",
  "version": "REPLACE_OBJECT_VERSION",
  "profile_sha256": "REPLACE_PROFILE_BYTES_SHA256",
  "source_manifest_sha256": "REPLACE_SOURCE_MANIFEST_SHA256",
  "review_status": "not_run",
  "observer": null,
  "observed_at": null,
  "items": [],
  "hypotheses": [],
  "reason": "尚未实际读取观察证据"
}
```

实际观察后写 observer.kind/id/receipt、带时区时间、items 和定位。not_applicable 使用 skipped 与实际理由。无用途推断无需造一个候选。观察条目示例结构为 id/kind/text/basis/limitations；假设为 id/text/status/based_on/reason。

## asset.md

下面是解析说明模板。仅 local 摘要模式把它复制为 .overview.md；OV/backend 模式由后端生成自己的摘要，不使用此复制规则。

```markdown
# {对象身份与源标题}

{同版摘要：是什么、提取范围、关键事实、必要未知与边界}

## 源事实

{事实与源声明，数值、单位、结构关系、来源定位和方法}
{总量/处理量/展示量，以及完整 facts 链接}

## 观察与推断

{真实观察及证据；未审阅/不适用时写明原因}
{推断明确标注未验证；无法判断时保留未知}

## 来源与方法

{源文件、依赖、facts、observations、profile、回执的相对链接}
{源快照与 profile 哈希、实际工具、能力范围}

## 限制

{损失、抽样、未支持内容，以及哪些变化会使验收失效}
```

仅 local 模式生成 .abstract.md，保留必要的否定、单位、未知和推断未验证标记。backend 模式在发布后读取后端 L0/L1，把实际 URI、版本、正文/哈希和检查保存到回执，remote.summaries 通过后才可声明 published。

## manifest.json

```json
{
  "schema_version": "general-parser.manifest.v1",
  "object_id": "REPLACE_OBJECT_ID",
  "version": "REPLACE_OBJECT_VERSION",
  "files": [{
    "path": "source/REPLACE_ORIGINAL_FILENAME",
    "role": "source",
    "sha256": "REPLACE_FILE_BYTES_SHA256",
    "size_bytes": 0
  }]
}
```

files 要枚举全部产物，排除 manifest.json 和 acceptance.json。上面仅示例一个条目；size_bytes 必须实测。

## acceptance.json

```json
{
  "schema_version": "general-parser.acceptance.v1",
  "object_id": "REPLACE_OBJECT_ID",
  "version": "REPLACE_OBJECT_VERSION",
  "manifest_sha256": "REPLACE_MANIFEST_BYTES_SHA256",
  "profile_sha256": "REPLACE_PROFILE_BYTES_SHA256",
  "source_manifest_sha256": "REPLACE_SOURCE_MANIFEST_SHA256",
  "state": "prepared",
  "checks": [
    {"id": "content.fidelity", "executed": false, "result": "unknown", "method": null, "evidence": [], "reason": "尚未核对"},
    {"id": "content.coverage", "executed": false, "result": "unknown", "method": null, "evidence": [], "reason": "尚未清点"},
    {"id": "document.consistency", "executed": false, "result": "unknown", "method": null, "evidence": [], "reason": "尚未核对正文"}
  ],
  "limitations": []
}
```

检查真实执行后才写 executed=true 和 pass，附方法和清单内回执。profile 增加的每个本地检查也要有记录；publication_checks 在发布阶段补记录，不能阻塞尚未发布的本地就绪状态。未知/失败不能通过改 state 升级为成功。
