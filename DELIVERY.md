# CareerLens AI 交付说明（DELIVERY）

本文档面向接手本项目的开发者与评审者，完整说明：

1. **架构设计与技术选型的取舍决策**——每个关键选择背后的考量、被否决的替代方案与最终依据；
2. **功能验证步骤**——可逐步复现的操作指南、预期结果与验证标准；
3. **已知缺口与后续优化方向**——如实列出未完成项，不隐瞒任何未实现需求。

> 配套文档：`README.md`（快速上手）、`AI_LOG.md`（开发过程对话归档）、`.github/workflows/ci.yml`（持续集成）。

---

## 1. 项目概述

CareerLens AI 是一个 AI 招聘 / 职业匹配系统，提供四项核心能力：

| 功能 | 前端入口 | 说明 |
| --- | --- | --- |
| 简历解析 | `/analyze` | 抽取关键词并给出综合评分 |
| 岗位匹配 | `/match` | 计算简历与 JD 的匹配度、优势与差距 |
| 简历优化 | `/optimize` | 给出评价、优化建议与缺失关键词 |
| 能力雷达 | `/radar` | 输出五维度能力评分 |

---

## 2. 架构设计与技术选型取舍

### 2.1 总体架构

```
浏览器
  │  HTTP
  ▼
frontend (Vue3 + Vite，Nginx 托管 / 反代 /api)
  │  /api/* → bff:3000
  ▼
bff (Node.js + Express + TypeScript，聚合层 + SQLite 持久化)
  │  /api/* → java-service:8080
  ▼
java-service (Spring Boot，字段映射 + 转发)
  │  /api/* → python-service:8000
  ▼
python-service (FastAPI，LLM 调用 + 业务逻辑)
  │  OpenAI-compatible API
  ▼
LLM（外部大模型服务）
```

**为什么是五层而不是四层？** 请求路径上共有 frontend / bff / java-service / python-service 四个自研服务 + 一个外部 LLM，共五段。每层职责单一，便于独立替换与测试。

### 2.2 关键决策清单

#### 决策 1：引入 BFF 层（Node/Express），而不是让前端直连 Java

- **考量因素**：前端需要「聚合 + 轻量持久化」能力；Java 侧重业务编排与强类型契约。
- **备选方案**：
  - A. 前端直连 Java：链路更短，但历史记录、结果规范化等逻辑会侵入 Java 或前端；
  - B. 引入 BFF：前端只与一个稳定契约交互，聚合逻辑内聚。
- **最终决策**：选 B。**依据**：BFF 承担参数校验、字段规范化（score 裁剪到 0–100）、SQLite 历史落库，使 Java 保持「纯转发 + 字段映射」的简单职责。

#### 决策 2：BFF 用 SQLite（better-sqlite3）而非关系型数据库

- **考量因素**：本项目为单体演示 / 小规模场景，需零外部依赖、开箱即用。
- **备选方案**：PostgreSQL / MySQL（需额外容器与运维）、纯内存（重启丢数据）。
- **最终决策**：better-sqlite3。**依据**：同步 API 简化代码、WAL 模式兼顾读写、单文件便于容器卷持久化（`DB_PATH=/app/data/careerlens.db`）。**代价**：不适合高并发写入，见第 4 节缺口。

#### 决策 3：保留 Java 层做「转发 + 字段映射」，而不是直接 BFF → Python

- **考量因素**：Java 承载企业侧契约稳定性与后续扩展（鉴权、审计、限流）。
- **备选方案**：BFF 直连 Python（少一跳，但丢失 Java 契约层）。
- **最终决策**：保留 Java 层。**依据**：项目明确要求展示多语言协作链路，且 Java 层负责**驼峰 ↔ 下划线字段映射**（如 `resumeText` ↔ `resume_text`），将命名差异收敛在一处。

#### 决策 4：LLM 调用收敛在 Python 层

- **考量因素**：AI 生态在 Python 最成熟（`openai` SDK、Pydantic 校验）。
- **备选方案**：在 BFF（Node）直接调用 LLM。
- **最终决策**：收敛在 Python。**依据**：Python 侧有完整的技能字典（`SKILL_ALIASES`，33 项）、`clamp_score` 归一化、`normalize_llm_skills` 语义兜底，形成「LLM 语义抽取 + 本地字典归一化」的稳定输出。

#### 决策 5：RestTemplate 字符集采用「覆盖索引 1」而非「追加转换器」

- **考量因素**：Python 返回 UTF-8 中文，Java 默认 `StringHttpMessageConverter` 为 ISO-8859-1，导致中文乱码 / 问号。
- **备选方案**：
  - A. `additionalMessageConverters(new StringHttpMessageConverter(UTF_8))`——**追加**到列表末尾；
  - B. `getMessageConverters().set(1, new StringHttpMessageConverter(UTF_8))`——**覆盖**默认转换器。
- **最终决策**：选 B。**依据**：Spring 按列表顺序匹配转换器，方案 A 追加的 UTF-8 转换器排在靠前的 ISO-8859-1 之后，永不命中；只有覆盖索引 1 才能生效。见 `java-service/.../config/PythonServiceConfig.java`。超时保留 连接 10s / 读取 120s，以适配 LLM 长链路。

#### 决策 6：容器编排采用「健康检查 + 依赖门控」的启动顺序

- **考量因素**：五段链路中下层未就绪会导致上层启动即失败。
- **最终决策**：`docker-compose.yml` 中自底向上用 `depends_on: condition: service_healthy` + 各服务 `healthcheck` 门控启动顺序（python → java → bff → frontend）。**依据**：避免竞态导致的启动失败，`start_period` 为慢启动服务预留窗口。

#### 决策 7：测试采用「离线可运行」策略

- **考量因素**：CI 环境无 LLM API Key、无外部下游；测试必须确定性、可独立复现。
- **最终决策**：
  - Python：`monkeypatch` 替换 `call_llm_json`；真实 LLM 冒烟用例用 `skipif` 在无 Key 时自动跳过；
  - BFF：替换 `callJavaHolder.callJava` 注入 mock，独立临时 SQLite；
  - Java：`MockRestServiceServer` 拦截 `RestTemplate`，不发起真实网络请求。
- **依据**：保证三端测试在任意环境 `pytest` / `npm test` / `mvn test` 均可离线通过。

#### 决策 8：Java 测试放弃 Mockito mock，改用可编程子类 / MockRestServiceServer

- **考量因素**：在 JDK 27 运行时下，Mockito inline mock maker 无法增强 `RestTemplate`（`Could not modify all classes`）。
- **最终决策**：使用 Spring 官方 `MockRestServiceServer` 绑定真实 `RestTemplate`。**依据**：不依赖字节码增强，跨 JDK 版本稳定，并支持对**转发请求体字段映射**的精确断言。

---

## 3. 功能验证步骤

> 约定：以下命令在仓库根目录 `careerlens-ai/` 执行；Windows PowerShell 环境。
> 服务端口：python 8000 / java 8080 / bff 3000 / 前端 5173。

### 3.1 前置：配置 LLM 环境变量

```powershell
# python-service/.env（参考 .env.example）
LLM_API_KEY=sk-xxxx
LLM_BASE_URL=https://api.openai.com/v1   # 或兼容网关
LLM_MODEL=gpt-4o-mini
```

**验证标准**：未配置时，业务接口会返回 `500` 且提示「LLM 调用失败」；配置正确后应返回 `200` 与真实中文结果。

### 3.2 本地开发模式启动（逐层验证）

#### 步骤 1：启动 Python 服务

```powershell
cd python-service
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
```

**预期结果**：控制台输出 `Uvicorn running on http://0.0.0.0:8000`。
**验证**：

```powershell
Invoke-RestMethod http://localhost:8000/health
# 期望：status=ok, service=careerlens-ai-python
```

#### 步骤 2：启动 Java 服务

```powershell
cd java-service
mvn spring-boot:run
```

**预期结果**：`Started JavaServiceApplication`。
**验证**：

```powershell
Invoke-RestMethod http://localhost:8080/api/health
# 期望：status=UP, service=java-service
```

#### 步骤 3：验证 Java → Python 的 UTF-8 中文透传（关键回归点）

```powershell
$body = '{"resumeText":"5年前端开发经验，熟悉Vue3与TypeScript"}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
Invoke-RestMethod -Uri http://localhost:8080/api/analyze -Method Post `
  -Body $bytes -ContentType "application/json; charset=utf-8"
```

**预期结果**：返回的 `keywords` 为**正常中文**（例如「前端开发」「TypeScript」），**不得出现 `??????` 或 `å±...` 等乱码**。
**验证标准**：`score` 在 0–100 之间，`keywords` 为语义化技能名。此步骤专用于回归「RestTemplate 字符集」修复。

> **注意（PowerShell 5 陷阱）**：必须使用 `[System.Text.Encoding]::UTF8.GetBytes($body)` 传字节，否则 PowerShell 会按 ISO-8859-1 编码请求体导致「假乱码」，这与 Java 无关。

#### 步骤 4：启动 BFF

```powershell
cd bff
npm install
npm run dev
```

**预期结果**：`BFF listening on http://localhost:3000`。
**验证**：

```powershell
Invoke-RestMethod http://localhost:3000/api/history?limit=1
# 期望：{ total, limit, records: [...] }
```

#### 步骤 5：启动前端

```powershell
cd frontend
npm install
npm run dev
```

**预期结果**：`Local: http://localhost:5173/`。
**验证**：浏览器打开 5173，逐页操作四个功能页。

### 3.3 端到端全链路验证（BFF 层汇总）

```powershell
# 简历解析
$b = [System.Text.Encoding]::UTF8.GetBytes('{"resume_text":"5年Java开发，熟悉Spring Boot与MySQL"}')
Invoke-RestMethod -Uri http://localhost:3000/api/analyze-resume -Method Post -Body $b -ContentType "application/json; charset=utf-8"

# 岗位匹配
$b = [System.Text.Encoding]::UTF8.GetBytes('{"resume_text":"3年前端","job_description":"要求React与性能优化"}')
Invoke-RestMethod -Uri http://localhost:3000/api/match-job -Method Post -Body $b -ContentType "application/json; charset=utf-8"

# 简历优化
$b = [System.Text.Encoding]::UTF8.GetBytes('{"resume_text":"3年前端","job_description":"要求React"}')
Invoke-RestMethod -Uri http://localhost:3000/api/optimize-resume -Method Post -Body $b -ContentType "application/json; charset=utf-8"

# 能力雷达
$b = [System.Text.Encoding]::UTF8.GetBytes('{"resume":"3年前端","jd":"要求React"}')
Invoke-RestMethod -Uri http://localhost:3000/api/radar -Method Post -Body $b -ContentType "application/json; charset=utf-8"

# 历史记录（应包含上述四类记录）
Invoke-RestMethod http://localhost:3000/api/history?limit=10
```

**验证标准**：

| 接口 | 期望状态码 | 期望响应要点 |
| --- | --- | --- |
| `/api/analyze-resume` | 200 | `keywords` 非空中文、`score` 0–100 |
| `/api/match-job` | 200 | `match_score` 0–100、`advantages`/`improvements` 数组 |
| `/api/optimize-resume` | 200 | `summary` 非空、`suggestions`/`missing_keywords` 数组 |
| `/api/radar` | 200 | `dimensions` 长度 5，每项 `score` 0–100 |
| `/api/history` | 200 | `records` 含 `analysis`/`match`/`optimization`/`radar` 四类 |

> **字段契约提醒**：`/api/radar`（BFF 与 Java 一致）使用 `resume` / `jd` 字段；其余三接口使用 `resume_text` / `job_description`。这是**前端已对齐的既定契约**，非缺陷。

### 3.4 数据持久化验证（SQLite）

**预期结果**：BFF 首次请求后会生成 `bff/data/careerlens.db`（容器内为 `/app/data/careerlens.db`）。
**验证标准**：`/api/history` 能返回历史记录；重启 BFF 后记录仍在；`docker-compose` 场景下 `bff-data` 卷保留数据。

### 3.5 Docker Compose 一键部署验证

```powershell
cd careerlens-ai
docker compose up -d --build
docker compose ps            # 四服务均应为 healthy
```

**验证标准**：

1. `docker compose ps` 显示 python/java/bff/frontend 四个容器 `healthy`；
2. 浏览器访问 `http://localhost:5173` 可正常使用四功能；
3. 反代生效：前端 `/api/*` 请求正确转发至 `bff:3000`；
4. `docker compose down` 后再 `up`，历史记录仍在（卷持久化）。

### 3.6 自动化测试验证（三端离线可运行）

```powershell
# Python
cd python-service
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -v
# 期望：19 passed（无 LLM_API_KEY 时真实冒烟用例自动跳过仍计入通过项）

# BFF
cd ..\bff
npm install
npm test
# 期望：Test Files 1 passed，Tests 18 passed

# Java
cd ..\java-service
mvn test
# 期望：Tests run: 10, Failures: 0, Errors: 0
```

**各测试套件覆盖情况**：

| 端 | 文件 | 用例数 | 覆盖内容 |
| --- | --- | --- | --- |
| Python | `python-service/tests/test_api.py` | 19 | 4 接口正常/异常、工具函数单测、真实 LLM 冒烟（条件跳过） |
| BFF | `bff/tests/api.test.ts` | 18 | 4 业务接口 + history 的正常/参数校验/下游失败/分数裁剪/持久化 |
| Java | `java-service/src/test/java/.../CareerControllerTest.java` | 10 | 4 接口 + health、字段映射断言、下游失败 500、空请求体边界 |

---

## 4. 已知缺口与后续优化方向

> 本节如实披露当前未完成 / 未实现的部分，供后续迭代排期。

### 4.1 已知缺口（未实现或未验证）

1. **前端自动化测试缺失**：`frontend/` 目前无单测 / E2E 测试，CI 仅对其做类型检查与构建，功能正确性依赖人工验证。
2. **README 端口与启动命令过时**：`README.md` 表格仍写 bff=8080 / backend=8081，实际为 bff=3000 / java-service=8080；且 python 启动命令写的是 `uvicorn app.main:app`（实际入口为根目录 `main.py`）。**待修正**。
3. **`backend/` 目录为骨架残留**：存在一个仅含 `HealthController`/`ServicePlaceholder` 的旧 Java 模块，未参与实际链路，属于历史遗留，建议清理或明确其用途。
4. **SQLite 并发能力有限**：better-sqlite3 为同步单写者模型，高并发写场景会成为瓶颈；当前仅适用于单实例 / 低并发。
5. **无鉴权与限流**：所有接口开放，缺少 API Key / JWT 鉴权、速率限制与配额控制，不适合直接暴露公网。
6. **LLM 调用无重试与降级缓存**：LLM 失败时仅返回 500 或本地字典兜底，未实现指数退避重试、结果缓存与熔断。
7. **历史记录无分页游标**：`/api/history` 仅支持 `limit`，无 offset / cursor 分页，大数据量下体验受限。
8. **测试未覆盖真实链路集成**：三端测试均为离线 mock；缺少 `docker compose` 级别的端到端集成测试（真实 LLM 需 Key，故默认不纳入 CI）。
9. **未配置日志聚合与监控**：仅有 docker json-file 日志（10m×3 轮转），无集中式日志、指标与告警。

### 4.2 后续优化方向

- **短期**：修正 README 端口/命令；为前端补充 Vitest 组件测试与 Playwright 冒烟；为 `/api/history` 增加分页。
- **中期**：引入统一鉴权（网关 / BFF 中间件）；LLM 调用增加重试、超时降级与结果缓存；SQLite 迁移评估（PostgreSQL）。
- **长期**：接入可观测性（OpenTelemetry + Prometheus + 日志聚合）；补齐 CI 的端到端集成测试；清理骨架残留模块。

---

## 5. 交付物清单

| 类别 | 文件 | 状态 |
| --- | --- | --- |
| 容器编排 | `docker-compose.yml`、四服务 `Dockerfile`、`frontend/nginx.conf`、`.dockerignore` | 已完成 |
| Python 测试 | `python-service/tests/test_api.py`、`pytest.ini`、`requirements-dev.txt` | 已完成（19 通过） |
| BFF 测试 | `bff/tests/api.test.ts`、`bff/vitest.config.ts`、`bff/package.json#test` | 已完成（18 通过） |
| Java 测试 | `java-service/src/test/java/com/careerlens/controller/CareerControllerTest.java` | 已完成（10 通过） |
| CI | `.github/workflows/ci.yml` | 已完成 |
| 文档 | `DELIVERY.md`、`AI_LOG.md`、`README.md` | 已完成（README 待修订，见 4.1） |
