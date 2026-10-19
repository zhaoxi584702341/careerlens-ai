# 03 · 项目级审查工作流（全仓库健康度）

> 适用：用户说「全项目审查」「整体架构评估」「项目健康度」「全面检查」。
> 前置：**必须先执行** `workflows/00-preflight.md`（Step A 判定粒度=项目级，Step B 排除无关目录，Step C 读取完整上下文）。

---

## 核心纪律：先分级，后聚焦

⚠️ **禁止**对全仓库逐文件平铺审查。必须**先按层/目录分级定位高风险区，再对高风险区深入，低风险区只做抽样**。

---

## 执行步骤

### 1. 建立仓库全景

- 顶层目录：`frontend/`、`bff/`、`java-service/`、`python-service/`、`contracts/`、`scripts/`、`.github/`、根配置（`docker-compose.yml` 等）。
- 排除 `node_modules/`、`dist/`、`build/`、`target/`、`.venv/`、`__pycache__/`、`coverage/`、`bff/data/`、`*.db` 等（详见 `workflows/00-preflight.md`（§B.2 必须排除的目录））。

### 2. 风险分级（先分级）

按下表给每个区域定级，**只有「高」区进入深度审查**：

| 风险等级 | 判定依据 | 本项目典型区域 |
| --- | --- | --- |
| 高 | 核心请求链、统一契约、共享状态、降级路径、并发/IO、安全边界 | `bff/src/app.ts`、`python-service/main.py`、`java-service/.../controller`、`contracts/openapi.yaml`、`frontend/src/stores/` |
| 中 | 业务逻辑与主要 UI、构建/交付配置 | 各 `views/`、`components/`、`Dockerfile`、`ci.yml`、`docker-compose.yml` |
| 低 | 文案、样例、静态资源、脚本 | `samples/`、`scripts/`（非关键路径） |

### 3. 聚焦深度审查（高区）

对每个高风险区，按 `references/dimensions.md` 执行**全量五维度**检查，并重点核查 `SKILL.md`（§七 项目专属审查要点）。

### 4. 中等风险区：抽样 + 针对性检查

- 抽查代表文件，重点看：错误处理、性能热点、测试覆盖、提交规范。

### 5. 交付与工程化专项（项目级必查）

| 项 | 检查内容 |
| --- | --- |
| Docker | 各 `Dockerfile` 是否多阶段/非 root/合理缓存；`docker-compose.yml` 服务依赖、healthcheck、卷、网络是否合理 |
| CI | `.github/workflows/ci.yml` 是否覆盖四端测试 + 构建 + 契约校验；触发分支与缓存策略是否合理 |
| 契约校验 | `scripts/validate-contracts.py` 是否纳入 CI；契约与实现是否一致 |
| 测试基线 | 四端测试是否可运行、是否与实现同步（前端 vitest / BFF vitest / Java JUnit / Python pytest） |
| 启动/关闭流程 | 是否与 `DELIVERY.md`、`.trae/rules/operations.md` 一致（端口/启动顺序） |

### 6. 架构评估（维度五）

- 分层是否清晰、职责是否单一、是否存在跨层耦合或绕过层级的直连。
- 五层链路职责边界是否被破坏（如前端直连 Java/Python、BFF 承担了 Java 的编排职责）。
- 契约是否为单一事实来源；是否存在契约与实现漂移。

---

## 输出

严格按 `references/report-template.md` 输出。项目级报告**必须包含**：

1. **审查范围**：覆盖的层/目录清单，说明已排除的目录。
2. **风险分级表**：各区域定级（高/中/低）及理由。
3. **高风险区深度问题清单**：按五维度分组（🔴/🟡/🟢 + 文件行号链接 + 修改建议）。
4. **工程化专项结论**：Docker / CI / 契约 / 测试 / 启动流程逐项结论。
5. **架构评估结论**：分层合理性、主要架构风险、建议的演进方向。
6. **优先级路线图**：按「先修 🔴 → 再优化 🟡」给出可执行的处理顺序。
