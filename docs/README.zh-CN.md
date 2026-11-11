# agent-memory-ledger（中文）

> **AI 智能体的可验证记忆层** —— 先写日志、哈希链留痕、软删除回收站、冲突台账、
> 写入锁、永久刚性规则，全部 **fail-closed（故障即拒绝）**。

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Tests](https://img.shields.io/badge/tests-63%20passed-green)
![Deps](https://img.shields.io/badge/runtime%20deps-0-green)
![Status](https://img.shields.io/badge/status-research%20prototype-orange)

> 研究报告级 / AI 辅助开发 · MIT 许可 · 维护者：`agent-memory-ledger maintainers`（中性署名）

---

大多数智能体记忆库帮你"**记得住**"；agent-memory-ledger 还帮你"**证明没记错、删得掉、
改得动、查得到**"——对需要被追责的智能体，提供**审计级记忆**。

## 为什么需要它

| 一般记忆库能 | agent-memory-ledger 额外能 |
|:--|:--|
| 存储/检索记忆 | **写前日志**：崩溃可重放，不丢数据 |
| 记住长对话 | **哈希链**：离线 `verify()` 可发现任何篡改 |
| 删除旧条目 | **软删除+回收站**：保留 30 天，可撤回 |
| 覆盖冲突值 | **冲突台账**：冲突显性化交给人工终审，绝不静默合并 |
| 任意写入 | **写入锁**：子 Agent 只写 `draft`，主控终审入 `core` |
| 记忆衰减 | **hard_rule**：永久刚性规则永不被衰减/归档/过滤 |

## 产品家族

同属 **Verifiable-agent 家族**（四个仓库同一套 fail-closed + 留痕设计语言）：

| 仓库 | 角色 |
|:--|:--|
| agent-call-audit | Agent 调用**审计引擎** |
| **agent-memory-ledger** | **记忆层**（本仓库） |
| agent-audit-gateway | 引擎的 HTTP **网关** |
| agent-route-grid | 多 Agent **路由编排** |

## 安装与 5 行示例

```bash
pip install agent-memory-ledger
# 或源码安装
pip install -e .
```

```python
from aml import MemoryStore, RecycleBin

store = MemoryStore("./mem")                       # 磁盘上 WAL + 哈希链
store.put({"layer": "core", "key": "redline", "payload": "no leverage"})
print(store.chain.verify())                        # (True, None, 1) 离线可验
bin = RecycleBin(store); bin.recycle("core", "redline"); bin.restore("redline")
```

## 8 条不变量（写进 README，外部可核）

1. 先 WAL 后提交：任何变更先追加日志，崩溃可重放
2. 写入三重校验：冲突 / 敏感 / 冗余 前置检查
3. 删除=软删除：进回收站保留 30 天，可撤回
4. 哈希链：`verify()` 重算全链，篡改必现
5. hard_rule 永久豁免：不衰减、不归档、不过滤
6. 写入锁：子级只能写 draft，主级终审入 core
7. 零敏感落盘：密钥/token 只存哈希或脱敏值
8. 冲突显性化：挂起等人工终审，绝不静默合并

## 安全与边界

- 参考实现（research prototype），生产使用前请自行审阅代码
- 漏洞请私信报告 `2307788504@qq.com`（勿开公开 issue）

## 相关

- 中文安装排障 / 贡献指南见 [CONTRIBUTING.md](../CONTRIBUTING.md)（英文）
- 家族体系：agent-call-audit（引擎）· agent-audit-gateway（网关）· agent-route-grid（路由）