# agent-memory-ledger（中文）


> **AI 智能体的可验证记忆层** —— 先写日志、哈希链留痕、软删除回收站、冲突台账、
> 写入锁、永久刚性规则，全部 **fail-closed（故障即拒绝）**。

```bash
pip install agent-audit-memory    # 零依赖，Python 3.9+
```

> **PyPI 包名说明**：PyPI 上本包发布名为 `agent-audit-memory`——原名
> `agent-memory-ledger` 在 PyPI 已被无关项目占用；且改名符合命名评审建议：
> `audit` 直指价值（可审计记忆），避开 `ledger` 的"账本/区块链"联想。
> 仓库名、导入路径（`import aml`）、CLI 及一切其他内容均不变。

> **发布策略**：外部种子用户验证窗口结束前，PyPI 以**预发布版**发布（`==0.2.0rc1` 等），
> 不作为 `latest`。预发布版适合原型验证，**不建议**用于处理敏感数据。
> 选型前请阅读 `docs/performance.md` 与 `docs/compliance.md`。

<a href="https://gitcode.com/gcw_MKhSyoGN/agent-memory-ledger"><img src="https://img.shields.io/badge/GitCode-gcw_MKhSyoGN%2Fagent-memory-ledger-blue" alt="GitCode"></a>
<a href="https://github.com/langarden/agent-memory-ledger"><img src="https://img.shields.io/badge/GitHub-langarden%2Fagent-memory-ledger-black" alt="GitHub"></a>

![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.9%2B-blue)
![Tests](https://img.shields.io/badge/tests-79%20passed-green)
![Deps](https://img.shields.io/badge/runtime%20deps-0-green)
![Status](https://img.shields.io/badge/status-research%20prototype-orange)

> 研究报告级 / AI 辅助开发 · MIT 许可 · 维护者：`agent-memory-ledger maintainers`（中性署名）

---

大多数智能体记忆库帮你"**记得住**"；agent-memory-ledger 还帮你"**证明没记错、删得掉、
改得动、查得到**"——对需要被追责的智能体，提供**审计级记忆**。

## 已知限制（请先读）

> ⚠️ v0.2 为研究原型。报 issue 前先看此表。

| # | 限制 | 影响 / 指引 |
|:--|:--|:--|
| 1 | 每存储目录**单进程写** | 独占锁强制，第二位写者抛 `ProcessContentionError`（含指引）。推荐一进程一目录，或每进程独立 `namespace=` |
| 2 | **不支持 NFS/网络共享盘** | 原子 rename 在其上不可靠，请用本地磁盘 |
| 3 | 文件存储容量上限 | 单 JSON 文件 ≤ 约 1 万条记忆；SQLite 后端在路标上 |
| 4 | **无读取侧权限控制** | `namespace=` 是数据隔离，**不是安全边界**；多租户生产需外层 OS 权限/ACL 兜底 |
| 5 | **非司法取证工具** | 删除证书/哈希链是内部完整性证明，不等同法庭证据（见 `docs/compliance.md`） |
| 6 | `durability="strict"` 慢 | 每条 fsync，仅适合审计场景，不适合高并发对话 Agent（见 `docs/performance.md`） |
| 7 | 链 `verify()` 为 O(n) | 约 10 万条以内够用；分段/快照校验在路标上 |

## 为什么需要它

| 一般记忆库能 | agent-memory-ledger 额外能 |
|:--|:--|
| 存储/检索记忆 | **写前日志**：崩溃可重放，不丢数据 |
| 记住长对话 | **哈希链**：离线 `verify()` 可发现任何篡改 |
| 删除旧条目 | **软删除+回收站**：保留 30 天，可撤回 |
| 覆盖冲突值 | **冲突台账**：冲突显性化交给人工终审，绝不静默合并 |
| 任意写入 | **写入锁**：子 Agent 只写 `draft`，主控终审入 `core` |
| 记忆衰减 | **hard_rule**：永久刚性规则永不被衰减/归档/过滤 |

### 它补的缺口

可靠性失败不是边缘案例。主流智能体记忆存储中反复出现的共性故障包括：

- **写失败导致记忆正文永久丢失**，且无处重试——正是「先 WAL 后提交 + 崩溃重放」要防的。
- **并发写入撕裂文件/破坏状态**（关停竞态、共享使用）——单一「追加式 WAL + 独占写入锁」消除这一整类失败。
- **单个损坏字符让整批候选静默失效**——静默损坏类失败，靠「哈希链 + 离线可验证留痕」能立刻暴露，而不是继续扩散。

这些是**可靠性与可验证性**问题，不是"更用力记"的问题。`agent-memory-ledger` 的设计保证：**每次写入先落日志再生效、每条记录哈希链离线可查、没有静默删除、没有冲突未经人工就合并**——即下方 10 条不变量。

## 不变量（10 条，外部可核）与持久化档位

1. 先 WAL 后提交：任何变更先追加日志，崩溃可重放
2. 写入三重校验：冲突 / 敏感 / 冗余 前置检查
3. 删除=软删除：进回收站保留 30 天，可撤回
4. 哈希链：`verify()` 重算全链，篡改必现
5. hard_rule 永久豁免：不衰减、不归档、不过滤
6. 写入锁：子级只能写 draft，主级终审入 core
7. 零敏感落盘：密钥/token 只存哈希或脱敏值
8. 冲突显性化：挂起等人工终审，绝不静默合并
9. **单写者强制**：每个存储目录独占跨进程锁（fail-closed），多进程同写会被拒
10. **可证明删除**：到期 purge 生成删除证书（仅含摘要、不含明文），明文物理清除

**持久化档位**（`durability=`）：`strict` 每条写入强制 fsync（断电零丢失，审计级）· `normal` 每次 flush（默认）· `fast` 跳过 fsync（仅供测试）。

## 并发与容量边界（当前文件后端）

- 每个存储目录**单进程写入**（独占锁强制，第二写入者抛 `ProcessContentionError`，不会撕裂文件）。v0.2 推荐姿势：一个 Agent 进程一目录；多进程共享 SQLite 后端在路标上。
- JSON 文件存储面向**单文件约 ≤1 万条**的记忆量；以上建议切未来 SQLite 后端（WAL 模式、事务化、可索引）。
- 哈希链 `verify()` 为 O(n) 线性校验：≤ 约 10 万条记录以内够用；更大规模的分段/快照校验在路标上。

## 合规说明（引用监管条文前请读）

本库提供**审计级记忆的技术底座**——WAL、哈希链留痕、软删除+可证明删除、写入锁。它**本身不**使系统"GDPR / EU AI Act 合规"：完整合规还需保留期限策略、读取侧访问控制、操作人员流程与组织制度。详见 `docs/compliance.md` 与 `RETAIN_ERASE_POLICY.md` 的能力边界说明。（2026-11 专家评审后校准）

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
pip install agent-audit-memory
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

## 安全与边界

- 参考实现（research prototype），生产使用前请自行审阅代码
- 漏洞请私信报告 `2307788504@qq.com`（勿开公开 issue）

## 商业服务（可选）

本库以 MIT 开源，正是为了让高保证场景的 Agent 团队**能亲自审查审计底座**——读 WAL、
哈希链、删除证书的代码，独立复现校验逻辑，跑完整测试。代码归你自由原型、fork、集成。

对于在受监管场景部署可审计 Agent 记忆的团队（EU AI Act 高风险系统、GDPR Art.17
删除留证、金融/保险工作流），我们围绕**开源内核**提供配套商业服务：

- **集成咨询**：LangGraph / LangChain 生产级接入、审计链路埋点、留存与删除策略设计；
- **合规落地支持**：把 `docs/compliance.md` 沉淀为客户可用的自评套件、审计证据导出
  流水线、删除证书归档方案；
- **企业增强版（闭源附加组件 / 订阅）**：多写者协调、RBAC 读取控制、审计事件推送、
  集中证书归档、监控控制台、对象存储适配、支持 SLA；
- **定制开发与年度支持**：区域监管适配（LGPD、国内数据合规）、自定义脱敏/存证对接、
  加急修复与安全补丁。

**信任内核（校验、删除证书、时序）永远完整开源**——商业价值在运维、规模、权限、
控制台与服务，不在隐藏信任逻辑。

**客户准入（刻意筛选，深度优先于广度）：**
- 团队**已明确**要做 EU AI Act / GDPR 高风险 Agent（而非好奇围观）；
- 团队内部**已有技术负责人与合规岗**（不由我们从零教 GDPR）；
- 已先跑通**开源版 POC**，确认与自身架构（LangGraph 优先）匹配；
- 我们**刻意只服务少量高价值标杆客户**——没有匹配度的咨询会礼貌引导回社区自助，
  不接零散/临时/频繁变更的小定制。

**服务边界（商业服务不含）：**
- 无 7×24 值班、无驻场、无无限需求变更；变更需求单独评估计费；
- 本库是**技术底座**，不是合规认证、不是法律取证凭证；最终监管责任由部署方承担
  （与仓库免责口径一致）。

商业咨询：`2307788504@qq.com`

## 相关

- 中文安装排障 / 贡献指南见 [CONTRIBUTING.md](../CONTRIBUTING.md)（英文）
- 家族体系：agent-call-audit（引擎）· agent-audit-gateway（网关）· agent-route-grid（路由）