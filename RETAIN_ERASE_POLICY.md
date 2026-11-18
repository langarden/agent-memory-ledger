# Retention & Erasure Policy（数据留存与删除说明）

> 版本：v1.0（2026-11-18）｜对应 GDPR Art.17（被遗忘权 / Right to erasure）的技术实现说明

## 1. 留存周期

| 数据 | 默认留存 | 可配置 | 说明 |
|:--|:--|:--|:--|
| 正常记忆（draft/hot/core/archive） | 永久（生命周期由应用管理） | 应用层归档策略 | 本库不主动过期业务记忆 |
| 回收站（recycled） | **30 天**（`DEFAULT_RETENTION`） | `RecycleBin(retention=...)` | 过期后 `purge_expired()` 才物理清除 |
| 删除证书（erasure certificates） | **永久**（append-only） | 归档导出 | 仅含摘要哈希，证明"曾存在+已删除" |
| WAL / 哈希链 | **永久**（append-only） | 归档导出 | 审计留痕，不随业务删除而删 |

## 2. 删除分两级（技术实现）

- **软删除（Recycle）**：`RecycleBin.recycle()` 将记录移入回收站，保留 30 天可撤回（`restore()`）。此阶段记录仍含明文。
- **可证明删除（Purge）**：`purge_expired()` 到期后：
  1. 从回收站移除该记录（明文消失）；
  2. 生成**删除证书**：`<base>/erasure/certificates.jsonl`，内容仅含 `payload_digest`（sha256 摘要）+ `erased_at` + `erased_by`；
  3. 哈希链追加 `purge` 标记（含摘要），供审计方离线验证"该条确曾存在、确已删除、明文不再可恢复"。

```python
from aml import MemoryStore, RecycleBin
store = MemoryStore("./mem")
bin = RecycleBin(store)
bin.recycle("core", "k")                 # 软删除，30 天内可撤回
certs = bin.purge_expired(erased_by="ops")  # 到期物理清除 + 删除证书
print(bin.read_certificates())           # [{'key': 'k', 'payload_digest': 'sha256…', ...}]
```

## 3. 法律边界（重要）

- 本库提供**删除留证的技术底座**（明文清除 + 摘要证书 + 可验证链）；
- **不构成**完整 GDPR 合规：还需企业配套的删除请求受理流程、保留期限策略、备份销毁制度、访问审计；
- 删除证书仅证明"本存储中该条已清除"，不替代企业级数据主权/备份策略。

## 4. 默认值速查

| 参数 | 默认 | 位置 |
|:--|:--|:--|
| `DEFAULT_RETENTION` | `30 * 24 * 3600`（30 天） | `aml/recycle.py` |
| `purge_expired(erased_by=...)` | `"system"` | `aml/recycle.py` |
| 证书目录 | `<base>/erasure/certificates.jsonl` | `RecycleBin(erasure_dir=...)` |

*编制：agent-memory-ledger maintainers｜2026-11-18｜专家评审后补充*