# 审计日志格式规范 · Audit Log Format Specification

> 版本：v1.0（2026-11-18）｜面向第三方审计工具/合规存档的字段标准化

## 0. 摘要算法与序列化规则（哈希可跨机器验证）

- **摘要算法**：SHA-256（`hashlib.sha256`）。
- **规范化序列化（canonical JSON）**：所有参与哈希/签名的对象一律
  `json.dumps(obj, sort_keys=True, ensure_ascii=False)`（key 排序、UTF-8、无多余空格），
  保证同一对象在任何机器/语言上产生完全相同的字节串，从而哈希一致。
- **哈希输入规则**：
  - WAL `rec_id` = SHA256(规范化 `op|key|layer|payload_hash|ts` 子集 JSON).hexdigest()[:16]
  - 链 `hash` = SHA256(规范化 payload JSON + `"|"` + prev_hash)
  - 删除证书 `payload_digest` = SHA256(规范化原始 payload JSON)
- ⚠️ **换算法警告（破坏性操作）**：本库默认固定 SHA-256。更换哈希算法会
  使全部历史链/证书校验失效（旧记录无法再 verify），属破坏性变更，仅可在
  显式迁移（重建链）时进行；文档会随版本注明当前算法。

## 1. 三种日志类型

| 类型 | 文件位置 | 内容 | 目的 |
|:--|:--|:--|:--|
| WAL（写前日志） | `<base>/wal/wal.log` | 每次变更的追加流水 | 崩溃重放、变更追溯 |
| 哈希链（trail） | `<base>/chain/chain.jsonl` | 链式留痕（lsn/hash/prev_hash） | 防篡改离线验证 |
| 删除证书 | `<base>/erasure/certificates.jsonl` | 可证明删除凭证 | GDPR Art.17 删除留证 |

## 2. WAL 记录字段（JSONL 每行一个 JSON）

```json
{
  "op": "put|promote|recycle|restore|purge",
  "key": "string",
  "layer": "draft|hot|core|archive",
  "payload_hash": "sha256（不落明文正文）",
  "ts": 1699999999.123,
  "rec_id": "操作记录短哈希（SHA256 前 16 位）"
}
```

**字段约束**：
- `rec_id` = SHA256(`op|key|layer|payload_hash|ts` 的 sort_keys JSON) 前 16 位；重放时校验，不匹配的尾部记录计为 `bad`（崩溃截断）。
- `op` 取值集合固定：`put` / `promote` / `recycle` / `restore` / `purge`。扩展操作需同步更新本规范。
- 明文正文**永不**出现在 WAL 中，只有 `payload_hash`（不变式 7）。

## 3. 哈希链记录字段

```json
{
  "lsn": 0,
  "index": 0,
  "ts": 1699999999.123,
  "payload": {"op": "put", "key": "redline", "payload_hash": "sha256..."},
  "prev_hash": "64-char-sha256 or 64 zeros (genesis)",
  "hash": "sha256(payload_json + '|' + prev_hash)"
}
```

**校验规则**（`chain.verify()`）：
- 每条 `hash` 必须等于重算值；
- `prev_hash` 必须等于上一条的 `hash`；
- `lsn` 必须等于行序号（0 起）；任一不符 → `verify() == (False, bad_index, total)`。

## 4. 删除证书字段

```json
{
  "key": "string",
  "from_layer": "draft|hot|core|archive",
  "erased_at": 1699999999.123,
  "erased_by": "system|ops|user-id",
  "payload_digest": "sha256（只留摘要证明存在）",
  "retention_seconds": 2592000
}
```

## 5. 外部审计对接建议

- 三种 JSONL 均可由合规取证脚本/第三方审计工具直接解析（每行独立 JSON，流式）。
- 审计方取数路径：WAL（变更流水）+ 链（完整性证明）+ 证书（删除证明）组合归档，建议与业务记忆分开保存（本库天然独立目录）。
- **本库产出技术日志，不替代企业级取证流程**：操作人身份、会话上下文、组织审批记录的关联由应用层负责。

*维护：agent-memory-ledger maintainers｜2026-11-18＊专家评审后标准化*