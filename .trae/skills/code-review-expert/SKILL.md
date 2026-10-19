---
name: code-review-expert
description: "代码审查智能助手。用于：发布上线前代码审查、发现代码逻辑缺陷、排查性能与稳定性隐患、检查代码规范、评估提交与架构。支持对 Git Diff、指定模块或整个项目进行审查。当用户提供代码、Git Diff 并要求审查、Review、检查 Bug、优化代码、上线前检查、项目级健康度分析时触发。"
version: "1.1.0"
---

# code-review-expert

面向 **CareerLens-AI** 项目的自研代码审查技能。覆盖「变更级（Git Diff）/ 模块级 / 项目级」三类审查粒度，统一遵循**五维审查框架**与**标准化输出规范**。

本技能**只做审查与建议**，不修改代码；除非用户显式要求修复。

---

## 一、目标技术栈

审查时按变更所在层套用对应的语言与框架规则：

| 层 | 位置 | 技术栈 | 测试框架 |
| --- | --- | --- | --- |
| 前端 | `frontend/` | Vue3 + TypeScript + Pinia + vue-router + Vite + Tailwind | vitest |
| 接入层 BFF | `bff/` | Node + Express + tsx + better-sqlite3 | vitest |
| 编排层 | `java-service/` | Java 17 + Spring Boot 3.2 + RestTemplate | JUnit + MockMvc |
| AI 能力层 | `python-service/` | Python 3.11+ + FastAPI + uvicorn + rules.py | pytest |
| 契约 | `contracts/` | OpenAPI 3.0.3 + JSON Schema + 错误码 | validate-contracts.py |
| 交付/运维 | 根目录 | Docker + Compose + GitHub Actions | — |

---

## 二、意图路由（Intention Routing）

路由分三步：**先确认审查意图（2.0）→ 再定粒度（2.1）→ 再定维度（2.2）**；无命中按 2.3 兜底，冲突按 2.4 消歧。

### 2.0 触发前置：审查意图（Trigger Intent）

**仅当用户同时具备「审查意图」时，本技能才路由生效。** 只出现 `commit`、`性能` 等词但无审查意图（如「帮我提交代码」「性能优化怎么做」）**不触发**。

| 意图关键词（中 / 英 / 同义，不区分大小写） |
| --- |
| 审查、评审、审阅、review、code review、检查、排查、评估、看看有没有问题、找问题、挑刺、把关 |
| 检查 Bug、找 bug、查错、有没有问题、潜在问题、隐患、风险点、correctness、有没有坑 |
| 上线前检查、发布前审查、发版前审查、pre-release、release check |
| 优化代码、优化建议、改进建议、improve、给点建议、refactor 建议 |
| 健康度、项目健康度、代码质量、质量评估、code health、audit、审计、技术债 |

### 2.1 第一步：判定审查粒度 → 载入对应工作流文件

| 粒度 | 触发关键词（不区分大小写，中/英/同义） | 载入工作流 |
| --- | --- | --- |
| 变更级 | diff、git diff、patch、变更、改动、改了、这次改的、本次变更、新增/修改/删除的文件、提交、commit、单个 commit、commit 区间、暂存、staged、unstaged、工作区、PR、MR、pull request、merge request、review my changes、changeset、HEAD | `workflows/01-diff-review.md` |
| 模块级 | 模块、组件、component、目录、文件夹、某个文件、文件名、某个服务、某一层、包、frontend/前端、bff/接入层、java-service/java、python-service/python、contracts/契约、stores/状态、src/、具体路径 | `workflows/02-module-review.md` |
| 项目级 | 整个项目、全项目、全仓库、仓库、repo、repository、代码库、codebase、整个工程、健康度/health、整体架构、架构评估、全面审查、全量审查、全局审查、项目级、audit | `workflows/03-project-review.md` |

判定规则：
1. **意图优先**：先过 2.0，无审查意图则不路由。
2. **强信号优先**：出现显式**路径/文件名** → 模块级；出现显式 **commit/区间/diff** → 变更级；出现**「整个/全/整体」** → 项目级。
3. **多粒度命中**：按 变更级 → 模块级 → 项目级 取**范围最小**者（由小到大逐级收敛）。
4. **粒度缺失**：仅命中维度或无任何粒度词 → 在 Step A 中确认；仍无法确定时默认 **变更级**（若当前无 Git 变更则升级为 **项目级**）。
5. **否定/纠正语义**：如「不要只看 diff，帮我看整个模块」→ 以**被肯定**的一方（模块级）为准。
6. 无论命中哪个工作流，**都必须先执行** `workflows/00-preflight.md` 的通用前置步骤。

### 2.2 第二步：判定审查维度 → 过滤检查点

维度关键词命中后，**只针对命中维度重点输出**，其余维度仅在发现严重问题时附带提及：

| 命中维度 | 触发关键词（不区分大小写，中/英/同义） | 对应检查点章节 |
| --- | --- | --- |
| 维度一 | 逻辑、Bug、bug、缺陷、defect、错误、error、需求匹配、边界、边界条件、edge case、异常、exception、空值/null、正确性、行为异常 | `references/dimensions.md`（§维度一 功能正确性与业务逻辑） |
| 维度二 | 性能、performance、慢、卡顿、延迟、latency、耗时、内存、memory、泄漏、leak、并发、concurrency、竞态、race condition、超时、timeout、降级、fallback、degradation、稳定性、stability、可用性、N+1、锁、lock | `references/dimensions.md`（§维度二 性能与稳定性） |
| 维度三 | 规范、风格、style、命名、naming、重复、冗余、duplication、可读性、readability、复杂度、complexity、注释、comment、文档、docs、lint、可维护性、maintainability | `references/dimensions.md`（§维度三 代码规范与可维护性） |
| 维度四 | 测试、test、单测、unit test、覆盖率、coverage、断言、assertion、监控、monitoring、日志、logging、可观测、observability、告警、alert、telemetry | `references/dimensions.md`（§维度四 测试覆盖与可观测性） |
| 维度五 | 提交、commit、提交信息、commit message、粒度、原子性、atomic、架构、architecture、分层、layering、耦合、coupling、依赖方向、模块划分 | `references/dimensions.md`（§维度五 提交规范与架构评估） |

**默认规则（关键）**：用户**未明确指定任何维度**时，执行**全量审查** —— 五个维度全部覆盖，不得遗漏任何维度。

> **`commit` 语义消歧**：`commit` 同时出现在 2.1 与维度五。用于界定**变更范围**（"这次 commit 改了什么"）→ 归入**粒度**（2.1）；用于评价**提交信息/提交粒度质量**（"commit 写得太粗"）→ 归入**维度五**。

### 2.3 兜底

若 2.0 的意图命中、但 2.1 / 2.2 的粒度与维度关键词**均未命中**，按 Step A 确认对象后进入 **项目级 + 全量五维度**。

### 2.4 边界用例与消歧优先级

| 边界情形 | 处理方式 |
| --- | --- |
| 同时命中多粒度 | 取**范围最小**者（变更级 > 模块级 > 项目级） |
| 同时命中多维度 | **全部纳入**（维度可叠加，非互斥） |
| 有维度、无粒度 | Step A 确认粒度；默认**变更级**（无 Git 变更 → 项目级） |
| 有粒度、无维度 | 默认**全量五维度** |
| `commit` 语义歧义 | 界定变更范围 → 粒度（2.1）；评价提交质量 → 维度五 |
| 否定/纠正语义 | 以**被肯定**的一方为准（如"别看 diff，看模块" → 模块级） |
| 中英混写 / 大小写 | 不区分大小写与中英，等价匹配 |
| 仅有意图、无对象 | Step A 询问对象；仍无法确定 → **项目级 + 全量五维度** |
| 无审查意图 | 不路由（见 2.0） |

---

## 三、执行流程总览

```
Step A 确认对象与范围（粒度：变更级 / 模块级 / 项目级）
   ↓
Step B 加载项目上下文（排除 node_modules、构建产物等无关目录）
   ↓
Step C 读取完整代码上下文（严禁只看片段下结论）
   ↓
载入 2.1 路由得到的工作流文件 → 按 2.2 的维度范围逐项检查
   ↓
按 references/report-template.md 输出中文 Markdown 报告
```

- Step A / B / C 的**标准化操作**见 `workflows/00-preflight.md`（权威定义，不得自行简化）。
- 每个工作流文件均引用本文件的 Step A/B/C，不重复定义。

---

## 四、五大审查维度（索引）

完整检查点清单见 `references/dimensions.md`，**每个维度下的检查点必须逐项覆盖，不得跳项**：

| 维度 | 名称 | 检查点主题 | 章节定位 |
| --- | --- | --- | --- |
| 维度一 | 功能正确性与业务逻辑 | 需求匹配、边界与异常处理、控制流清晰度 | `references/dimensions.md`（§维度一 功能正确性与业务逻辑） |
| 维度二 | 性能与稳定性 | 资源消耗、IO/数据库操作、并发与锁、依赖服务超时降级 | `references/dimensions.md`（§维度二 性能与稳定性） |
| 维度三 | 代码规范与可维护性 | 命名格式、复杂度与重复、注释与文档 | `references/dimensions.md`（§维度三 代码规范与可维护性） |
| 维度四 | 测试覆盖与可观测性 | 测试充分性、监控与日志 | `references/dimensions.md`（§维度四 测试覆盖与可观测性） |
| 维度五 | 提交规范与架构评估 | 提交粒度、架构合理性 | `references/dimensions.md`（§维度五 提交规范与架构评估） |

---

## 五、输出规范（强制）

报告模板、严重程度定义与证据规范见 `references/report-template.md`。核心要求：

1. **语言与格式**：使用**中文 Markdown**，严格按模板章节组织。
2. **分级**：所有问题必须归入三类之一：
   - 🔴 **必须修复** —— 阻塞上线：功能性缺陷、数据/安全风险、核心链路回归。
   - 🟡 **建议优化** —— 非阻塞：可维护性、性能优化、规范问题。
   - 🟢 **亮点** —— 值得肯定与推广的实践。
3. **可定位**：每个问题必须标注**具体文件路径与行号**，并使用可点击链接，例如：
   `[app.ts](file:///c:/Users/admin/Desktop/boss-demo/careerlens-ai/bff/src/app.ts#L41-L52)`。
   **禁止**只写「某处」「大概在 XX 行」。
4. **可落地**：必须给出**修改建议或示例代码**，不能只描述问题。
5. **不臆断**：证据不足或逻辑不确定的问题，必须显式标注「**待确认**」并说明需要补充什么信息，**禁止猜测性下结论**。
6. **不泄密**：报告中**禁止**出现密钥、Token、密码、连接串、`.env` 内容等敏感信息；发现敏感信息只描述「存在未脱敏的凭据，位置 X」，不回显具体值。

---

## 六、纪律约束（强制，违反即视为审查失败）

1. **禁止脱离上下文下结论**：必须读取完整的函数/文件/调用方上下文后再判定；不得基于代码片段、文件名或直觉断言。
2. **严格区分事实与建议**：事实（客观缺陷、可复现错误）与建议（主观优化、风格偏好）必须在报告中分开陈述，建议不得伪装成事实。
3. **评估核心链路的回归风险**：涉及请求链（前端 → BFF → Java → Python → LLM）或共享契约的改动，必须评估对**上下游与既有功能**的回归影响，并明确指出影响面。
4. **验证变更范围**：审查结论必须基于**真实的变更范围**（`git diff` / 指定模块边界），不得把未改动代码当作本次变更问题；区分「本次引入」与「历史遗留」。
5. **项目级审查必须先分级后聚焦**：不得对全仓库逐文件平铺。必须**先按层/目录分级定位高风险区**，再对高风险区深入；低风险区只做抽样。
6. **不修改代码**：默认只输出审查报告；确需修复时，须经用户显式确认后再动手。

---

## 七、项目专属审查要点（CareerLens-AI 增强）

在五维度通用检查点之外，本项目**必须额外核查**以下项：

| 要点 | 说明 | 关注位置 |
| --- | --- | --- |
| 契约一致性 | `contracts/openapi.yaml` 与四层实现字段/错误码是否一致；新增字段是否同步更新契约 | `contracts/`、各层接口 |
| 双字段名兼容 | Java 转发层用驼峰（`resumeText`/`jobDescription`），前端/BFF 用蛇形（`resume_text`/`job_description`），两侧是否都正确兼容 | `java-service`、`bff`、`frontend/src/api` |
| 降级路径 | LLM 失败须返回 HTTP 200 + 规则层结果，`meta.degraded=true`、`meta.aiMode=rule`；不得抛 5xx 或丢字段 | `python-service/main.py` |
| 统一响应契约 | 四个业务接口是否统一返回 `success` / `meta{timings,degraded,aiMode}`；BFF 是否补齐 `meta.timings.bff` | `bff/src/app.ts`、`python-service/main.py` |
| 前端状态共享 | Pinia store 是否保持「单一数据源 + localStorage 持久化 + 跨标签页同步 + 静默降级」范式；是否残留本地 `ref` 造成多份状态 | `frontend/src/stores/`、各视图 |
| 进程与端口纪律 | 审查**不得**触碰进程；不得建议无谓重启；端口/启动顺序须符合 `.trae/rules/operations.md` | `.trae/rules/operations.md` |

---

## 八、文件索引（唯一权威，引用必须与此完全一致）

```
.trae/skills/code-review-expert/
├── SKILL.md                          # 本文件：路由、流程总览、输出规范、纪律约束
├── workflows/
│   ├── 00-preflight.md               # 通用前置步骤 Step A / B / C（三种粒度共用）
│   ├── 01-diff-review.md             # 变更级审查工作流（Git Diff）
│   ├── 02-module-review.md           # 模块级审查工作流（指定目录/服务/文件）
│   └── 03-project-review.md          # 项目级审查工作流（全仓库健康度）
└── references/
    ├── dimensions.md                 # 五大审查维度完整检查点清单
    └── report-template.md            # 中文 Markdown 报告模板、分级与证据规范
```

> 所有内部引用一律使用**相对于本技能根目录**的路径（如 `workflows/00-preflight.md`）。
>
> **引用格式约定**：文件之间只引用**文件路径**，跨文件的章节定位统一写作 `` `路径`（§章节号 标题） ``，例如 `` `workflows/00-preflight.md`（§B.2 必须排除的目录） ``、`` `references/dimensions.md`（§维度一 功能正确性与业务逻辑） ``。不使用 `#fragment` 锚点，避免中文/标点导致锚点漂移。若某引用路径与实际文件不符，以本索引为准并修正引用。
