# Performance Notes（性能基线）

> 版本：v1.0（2026-11-18）｜实测基线，供选型参考，非基准测试竞赛。

## 1. 实测基线（1000 次写入单条）

**测试环境**：Windows 10（AMD64），Python 3.13，本地磁盘；`examples/bench.py` 微基准，
单条 `put()`（含 WAL append + 哈希链 append + JSON 持久化）。

| durability | ms/write | writes/sec | 相对 fast |
|:--|:--|:--|:--|
| fast | ~23.5 | ~43 | 1.00x |
| normal | ~24.9 | ~40 | 1.06x |
| strict | ~26.0 | ~39 | 1.11x |

**结论**：
- 三档差异不大（strict 比 fast 慢约 10%）——v0.2 文件后端的主要开销是每次写入都做
  JSON 全量持久化 + 哈希计算 + 文件 fsync，而非单条 fsync 本身。
- `strict` 是**安全优先**档位（断电零丢失、审计级），适合合规审计场景；
- `fast` 仅适合测试/原型，**不建议生产**；
- 规模说明：以上为单机小文件后端。高并发对话型 Agent（每秒数十写）建议走
  `normal`，并考虑 v0.3 SQLite 后端（WAL 模式、批量事务、索引）以获得更好吞吐。

## 2. 何时用哪档

| 场景 | 推荐 durability |
|:--|:--|
| 合规审计、金融/政务留痕 | `strict`（可接受慢，不可丢） |
| 常规 Agent 记忆（原型/中小规模） | `normal`（默认，平衡） |
| 单元测试/本地 demo | `fast` 或不指定 |

## 3. 容量提示（与 README Known Limitations 一致）

- JSON 文件后端：单文件 ≤ ~1 万条记忆较舒适；超过后加载/校验变慢。
- 大规模/多进程写：v0.3 SQLite 后端（触发条件见 `docs/compliance.md`）。

*维护：agent-memory-ledger maintainers｜2026-11-18｜专家评审 #2 要求量化基线*