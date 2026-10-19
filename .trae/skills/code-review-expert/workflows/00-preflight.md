# 00 · 通用前置步骤（Step A / B / C）

> 权威定义。`workflows/01-diff-review.md`、`workflows/02-module-review.md`、`workflows/03-project-review.md` **均必须先执行本文件的三个步骤**，不得跳过或简化。

---

## Step A：确认审查对象与范围（三种粒度）

先判定用户诉求属于哪一粒度，并明确边界后再动手。

| 粒度 | 审查对象 | 边界定义 | 典型采集命令 |
| --- | --- | --- | --- |
| **变更级** | 本次代码变更 | 工作区变更 + 暂存区变更（或用户指定的某个 commit / commit 区间） | `git status -s`、`git diff`、`git diff --staged`、`git diff <base>...HEAD`、`git log --oneline -n 20` |
| **模块级** | 指定目录 / 服务 / 文件 | 用户点名的路径（如 `bff/`、`python-service/main.py`、`frontend/src/stores/`）及其**直接依赖/被依赖的相邻文件** | `Glob` 按路径列举、`Grep` 定位引用方 |
| **项目级** | 全仓库 | 仓库全部源码（排除无关目录，见 §Step B），**先分级后聚焦** | 顶层目录结构 + 各层入口文件 |

### Step A 动作清单

1. **判定粒度**：依据 `SKILL.md`（§2.1 第一步：判定审查粒度 → 载入对应工作流文件）。
2. **明确边界**：
   - 变更级：确认基准（工作区 / 暂存区 / 指定 commit）；**必须记录基准**，避免把历史遗留当作本次引入。
   - 模块级：确认具体路径；若用户只说「某个模块」而未给出路径，**先询问或从对话中提取**，不得自行扩大范围。
   - 项目级：确认是否要覆盖全部层（前端/BFF/Java/Python/契约/交付）。
3. **确认维度范围**：依据 `SKILL.md`（§2.2 第二步：判定审查维度 → 过滤检查点）；**未指定维度 → 全量五维度**。
4. **无法判定时**：向用户澄清一次（粒度 + 边界 + 维度）；仍不确定则按 `SKILL.md`（§2.1 规则 4）兜底。

> ⚠️ 纪律：范围一旦确定，**不得在审查中途自行扩大或缩小**；如需调整，必须在报告中说明。

---

## Step B：加载项目上下文并排除无关目录

### B.1 必读上下文（按需）

| 内容 | 位置 | 用途 |
| --- | --- | --- |
| 项目约定/规则 | `.trae/rules/`（含 `operations.md`） | 进程/端口/操作纪律 |
| 架构与交付说明 | `DELIVERY.md`、`README.md` | 架构取舍、已知缺口、启动方式 |
| 接口契约 | `contracts/openapi.yaml`、`contracts/*.schema.json`、`contracts/error-codes.md` | 字段/错误码一致性基线 |
| 各层入口 | `frontend/src/main.ts`、`bff/src/index.ts`、`bff/src/app.ts`、`java-service/src/main/java/**`、`python-service/main.py` | 请求链与真实实现 |
| 构建与 CI | `docker-compose.yml`、`.github/workflows/ci.yml`、各层 `Dockerfile` | 交付与流水线 |

### B.2 必须排除的目录（不得纳入审查，也不得作为证据来源）

```
node_modules/      dist/            build/          target/          .venv/  venv/
__pycache__/       .pytest_cache/   coverage/       .git/            .idea/  .vscode/
*.min.js           *.map            bff/data/       *.db  *.db-wal  *.db-shm
```

- 上述内容属于**依赖、构建产物、缓存、本地数据或编辑器配置**，不参与代码质量判定。
- 若变更恰好落在被排除目录内（如误提交 `dist/`），**记为一个问题**（见维度五/交付），但不对其内容做代码审查。

### B.3 排除后仍要保留的内容

- 源码（`*.ts`、`*.vue`、`*.java`、`*.py` 等）、配置（`*.yml`/`*.json`/`Dockerfile`）、契约、CI、文档。

---

## Step C：读取完整代码上下文（禁止片段臆断）

1. **读整段而非片段**：定位到问题行后，必须读取其所在的**完整函数/方法**，必要时读取整个文件。
2. **读上下游**：
   - 被调方：确认参数、返回、异常语义。
   - 调用方：确认是否所有调用点都受影响（`Grep` 全量检索符号）。
   - 跨层：改动若在契约/字段层面，需**同时核对相邻层的对应实现**（前端 ↔ BFF ↔ Java ↔ Python）。
3. **读历史**：严重问题需回看 `git log`/`git blame`，判断是**本次引入**还是**历史遗留**，并在报告中标注。
4. **可复现再断言**：能本地验证的（跑测试、读配置、比对契约）尽量验证；无法验证的标注「**待确认**」。

> ⚠️ 纪律：**任何未读取完整上下文就给出的结论，视为无效结论**，必须撤回。

---

## 完成后

完成 Step A / B / C 后，回到 `SKILL.md`（§三 执行流程总览），载入 §2.1 路由得到的具体工作流文件继续执行。
