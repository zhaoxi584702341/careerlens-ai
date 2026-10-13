# CareerLens AI 交付说明（DELIVERY）

本文档面向接手本项目的开发者与评审者，如实说明：

1. **架构设计与技术选型的取舍决策**——每个关键选择背后的考量、被否决的替代方案与最终依据；
2. **本次实际验证过的启动、测试、部署/回滚步骤**——标注每项的**真实执行结果**，未通过或受环境限制的项单独说明；
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

## 2. 本次实测结果汇总（先看结论）

下表为本次交付**真实执行**的验证结果，后续章节给出可复现命令。

| # | 验证项 | 命令 | 实测结果 |
| --- | --- | --- | --- |
| 1 | BFF 类型检查 | `npm run type-check`（bff/） | ✅ 通过（exit 0） |
| 2 | BFF 单元/接口测试 | `npm test`（bff/） | ✅ **19 passed**（1 file） |
| 3 | Python 接口测试 | `.\.venv\Scripts\python.exe -m pytest`（python-service/） | ✅ **21 passed** |
| 4 | Java 测试 | `mvn -B test`（java-service/） | ✅ **10 passed**，BUILD SUCCESS |
| 5 | 前端测试 | `npm test`（frontend/） | ✅ **30 passed**（3 files） |
| 6 | 前端构建 | `npm run build`（frontend/） | ✅ 成功（约 8.2s） |
| 7 | 契约校验 | `.\.venv\Scripts\python.exe ..\scripts\validate-contracts.py` | ✅ **PASS=19 FAIL=0** |
| 8 | Compose 配置校验 | `docker compose config` | ✅ 通过，四服务渲染正常 |
| 9 | Compose 完整构建启动 | `docker compose up -d --build` | ❌ **失败**：Docker Hub 网络不可达（环境限制，非配置缺陷，详见 4.1-1） |

**结论**：四项测试套件 + 前端构建 + 契约校验 + Compose 配置全部实跑通过；唯一的 Compose 完整启动因当前环境无法访问 Docker Hub 而未能完成，已在第 4 节如实披露。

---

## 3. 架构设计与技术选型取舍

### 3.1 总体架构

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

### 3.2 关键决策清单

#### 决策 1：引入 BFF 层（Node/Express），而不是让前端直连 Java

- **考量因素**：前端需要「聚合 + 轻量持久化」能力；Java 侧重业务编排与强类型契约。
- **备选方案**：
  - A. 前端直连 Java：链路更短，但历史记录、结果规范化等逻辑会侵入 Java 或前端；
  - B. 引入 BFF：前端只与一个稳定契约交互，聚合逻辑内聚。
- **最终决策**：选 B。**依据**：BFF 承担参数校验、字段规范化（score 裁剪到 0–100）、SQLite 历史落库，使 Java 保持「纯转发 + 字段映射」的简单职责。

#### 决策 2：BFF 用 SQLite（better-sqlite3）而非关系型数据库

- **考量因素**：本项目为单体演示 / 小规模场景，需零外部依赖、开箱即用。
- **备选方案**：PostgreSQL / MySQL（需额外容器与运维）、纯内存（重启丢数据）。
- **最终决策**：better-sqlite3。**依据**：同步 API 简化代码、WAL 模式兼顾读写、单文件便于容器卷持久化（`DB_PATH=/app/data/careerlens.db`）。**代价**：不适合高并发写入，见第 5 节缺口。

#### 决策 3：保留 Java 层做「转发 + 字段映射」，而不是直接 BFF → Python

- **考量因素**：Java 承载企业侧契约稳定性与后续扩展（鉴权、审计、限流）。
- **备选方案**：BFF 直连 Python（少一跳，但丢失 Java 契约层）。
- **最终决策**：保留 Java 层。**依据**：项目明确要求展示多语言协作链路，且 Java 层负责**驼峰 ↔ 下划线字段映射**（如 `resumeText` ↔ `resume_text`），将命名差异收敛在一处。

#### 决策 4：LLM 调用收敛在 Python 层

- **考量因素**：AI 生态在 Python 最成熟（`openai` SDK、Pydantic 校验）。
- **备选方案**：在 BFF（Node）直接调用 LLM。
- **最终决策**：收敛在 Python。**依据**：Python 侧有完整的技能字典（`SKILL_ALIASES`）、`clamp_score` 归一化、`normalize_llm_skills` 语义兜底，形成「LLM 语义抽取 + 本地字典归一化」的稳定输出。

#### 决策 5：LLM 失败时返回 200 + 降级结果，而不是 500

- **考量因素**：演示 / 教学场景下，LLM 网关不可用（无 Key、超时、限流）时若直接 500，前端四个功能页全部白屏，体验与可演示性极差。
- **备选方案**：
  - A. 沿用常规做法返回 `500`，由前端提示错误；
  - B. 返回 `200` + 本地降级结果（技能字典 / 集合交并差 / 空结构）。
- **最终决策**：选 B（仅限 Python 业务四接口）。**依据**：`analyze` 降级为本地字典 `extract_skills()`（score=0）、`match` 降级为技能集合交并差、`optimize`/`radar` 降级为可控空结构；**且响应体 `meta.degraded=true`、`meta.aiMode=rule` 显式标记降级**，调用方可据此判断是否走了真实 LLM。**注意**：Java 层下游失败仍返回 `500`（契约不同，见 4.1-3）。

#### 决策 6：RestTemplate 字符集采用「覆盖索引 1」而非「追加转换器」

- **考量因素**：Python 返回 UTF-8 中文，Java 默认 `StringHttpMessageConverter` 为 ISO-8859-1，导致中文乱码 / 问号。
- **备选方案**：
  - A. `additionalMessageConverters(new StringHttpMessageConverter(UTF_8))`——**追加**到列表末尾；
  - B. `getMessageConverters().set(1, new StringHttpMessageConverter(UTF_8))`——**覆盖**默认转换器。
- **最终决策**：选 B。**依据**：Spring 按列表顺序匹配转换器，方案 A 追加的 UTF-8 转换器排在靠前的 ISO-8859-1 之后，永不命中；只有覆盖索引 1 才能生效。见 `java-service/src/main/java/com/careerlens/config/PythonServiceConfig.java`。超时保留 连接 10s / 读取 120s，以适配 LLM 长链路。

#### 决策 7：容器编排采用「健康检查 + 依赖门控」的启动顺序

- **考量因素**：五段链路中下层未就绪会导致上层启动即失败。
- **最终决策**：`docker-compose.yml` 中自底向上用 `depends_on: condition: service_healthy` + 各服务 `healthcheck` 门控启动顺序（python → java → bff → frontend）。**依据**：避免竞态导致的启动失败，`start_period` 为慢启动服务预留窗口。

#### 决策 8：测试采用「离线可运行」策略

- **考量因素**：CI 环境无 LLM API Key、无外部下游；测试必须确定性、可独立复现。
- **最终决策**：
  - Python：`monkeypatch` 替换 `call_llm_json`；真实 LLM 冒烟用例用 `skipif` 在无 Key 时自动跳过；
  - BFF：替换 `callJavaHolder.callJava` 注入 mock，独立临时 SQLite；
  - Java：`MockRestServiceServer` 拦截 `RestTemplate`，不发起真实网络请求；
  - 前端：Vitest 组件 / store / api 模块测试。
- **依据**：保证四端测试在任意环境均可离线通过（本次实测结果印证：19 / 18 / 10 / 30 全绿）。

#### 决策 9：Java 测试放弃 Mockito mock，改用 MockRestServiceServer

- **考量因素**：在高版本 JDK 运行时下，Mockito inline mock maker 无法增强 `RestTemplate`（`Could not modify all classes`）。
- **最终决策**：使用 Spring 官方 `MockRestServiceServer` 绑定真实 `RestTemplate`。**依据**：不依赖字节码增强，跨 JDK 版本稳定，并支持对**转发请求体字段映射**的精确断言。

---

## 4. 实际验证过的启动 / 测试 / 部署 / 回滚

> 约定：以下命令在仓库根目录 `careerlens-ai/` 执行；Windows PowerShell 环境。
> 服务端口：python 8000 / java 8080 / bff 3000 / 前端 5173（容器内 nginx 80）。

### 4.1 前置：配置 LLM 环境变量

```powershell
# python-service/.env（参考 .env.example，该文件不入库）
LLM_API_KEY=sk-xxxx
LLM_BASE_URL=https://re.94xy.cn/v1   # 或其它 OpenAI 兼容网关
LLM_MODEL=gpt-5.6-sol
```

**行为说明**：未配置 Key 时，Python 业务四接口**仍返回 200**，但走本地降级逻辑（见决策 5），`/health` 的 `llm_enabled=false`。

### 4.2 自动化测试验证（四端离线可运行）— 已实测

```powershell
# Python（21 passed）
cd python-service
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -v

# BFF（type-check 通过 + 19 passed）
cd ..\bff
npm ci
npm run type-check
npm test

# Java（10 passed，BUILD SUCCESS）
cd ..\java-service
mvn -B test

# 前端（30 passed + 构建成功）
cd ..\frontend
npm ci
npm test
npm run build

# 契约校验（PASS=19 FAIL=0）
cd ..\python-service
.\.venv\Scripts\python.exe ..\scripts\validate-contracts.py
```

**各测试套件覆盖情况**：

| 端 | 测试文件 | 用例数 | 覆盖内容 |
| --- | --- | --- | --- |
| Python | `python-service/tests/test_api.py` | 21 | 4 接口正常/降级、契约字段（meta/level/hits/gaps/qualityIssues/skills）、驼峰字段兼容、工具函数单测、真实 LLM 冒烟（条件跳过） |
| BFF | `bff/tests/api.test.ts` | 19 | 4 业务接口 + history 的正常/参数校验/下游失败/分数裁剪/持久化、契约字段透传与 meta 补齐 |
| Java | `java-service/src/test/java/.../CareerControllerTest.java` | 10 | 4 接口 + health、字段映射断言、下游失败 500、空请求体边界 |
| 前端 | `frontend/src/{stores,components,api}/*.spec.ts` | 30 | store 状态流转、组件渲染、api 层封装（3 个 spec 文件） |

### 4.3 本地开发模式启动（逐层验证）

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
# 期望：status=ok, service=careerlens-ai-python, llm_enabled=<bool>
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

**预期结果**：返回的 `keywords` 为**正常中文**（例如「前端开发」「TypeScript」），**不得出现 `??????` 或乱码**。此步骤专用于回归决策 6 的「RestTemplate 字符集」修复。

> **注意（PowerShell 5 陷阱）**：必须使用 `[System.Text.Encoding]::UTF8.GetBytes($body)` 传字节，否则 PowerShell 会按 ISO-8859-1 编码请求体导致「假乱码」，这与 Java 无关。

#### 步骤 4：启动 BFF

```powershell
cd bff
npm ci
npm run dev
```

**预期结果**：`BFF listening on http://localhost:3000`。
**验证**：

```powershell
Invoke-RestMethod http://localhost:3000/api/history?limit=1
# 期望：{ total, limit, records: [...] }
```

> **入口文件说明**：BFF 的启动入口是 `bff/src/index.ts`，它只负责监听端口；应用本体（路由、Java 转发、契约 `meta` 组装、SQLite 持久化）全部定义在 `bff/src/app.ts`（导出 `app`，同时被 vitest 直接引用）。两者刻意分离，保证「可测试的 app」与「可运行的进程」职责单一。`npm run dev` / `npm start` / Dockerfile 均指向 `index.ts`。

#### 步骤 5：启动前端

```powershell
cd frontend
npm ci
npm run dev
```

**预期结果**：`Local: http://localhost:5173/`。
**验证**：浏览器打开 5173，逐页操作四个功能页。

### 4.3.1 启动顺序与启动前检查（实测）

**严格顺序：Python(8000) → Java(8080) → BFF(3000) → 前端(5173)。** 后层依赖前层，关闭时反向。启动前先确认四端口空闲，避免与残留实例叠加（本项目约定「先关后开、禁止同端口多实例」）：

```powershell
Get-NetTCPConnection -State Listen -LocalPort 8000,8080,3000,5173 -ErrorAction SilentlyContinue
# 无输出 = 四端口空闲，可继续；有输出则先停掉占用进程
```

### 4.3.2 启动常见异常与处理（实测踩坑记录）

| 现象 | 根因 | 处理 |
| --- | --- | --- |
| BFF 启动报 `Error: Cannot find module '...\bff\node_modules\tsx\dist\cli.mjs'` | `bff/node_modules` 依赖不完整，`tsx` 未安装（`npm run dev` 用 `tsx watch` 运行 TS 入口） | 先 `cd bff; npm install`（或 `npm ci`），再 `npm run dev` |
| Python 启动报 `No module named 'uvicorn'` / `No module named 'rules'` | 未用项目虚拟环境，或启动目录不是 `python-service` | 必须用 `.\.venv\Scripts\python.exe -m uvicorn main:app ...`，且 `cd python-service` 后执行 |
| Python `pytest` 找不到 | 用了系统 Python 或 `venv`（非 `.venv`） | 统一用 `.venv\Scripts\python.exe -m pytest`（仅 `.venv` 装了 dev 依赖） |
| Java 启动报 `Port 8080 was already in use` | 端口被残留实例占用 | 先释放对应端口再启动（禁止叠加实例） |
| BFF `/api/history` 返回 `Cannot GET` | 跑的是旧 mock 入口，未指向 `app.ts` | 确认 `bff/src/index.ts` 已 `import { app } from './app.js'`，重启 BFF |
| 前端页面能开但接口 404/500 | 后端链路未就绪（BFF/Java/Python 有未起者） | 按序自检 8000→8080→3000 健康检查 |
| LLM 相关功能恒降级（`meta.aiMode=rule`） | `python-service/.env` 缺 LLM 三项配置 | 补齐 `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL` 后重启 Python；仅离线演示可显式设 `AI_MODE=rule` |

> **依赖安装须早于启动**：四个服务的依赖相互独立，但必须在启动对应服务前完成（Python `pip install -r requirements.txt`、Java `mvn dependency:resolve`、BFF/前端 `npm ci`）。本次实测即因 `bff` 依赖缺失导致首次 `npm run dev` 失败，补装后恢复。

> **前端预览**：Vite 默认绑定 `localhost`，浏览器访问 `http://localhost:5173/`；若 5173 被占用，Vite 会自动改用 5174 等端口（以启动日志 `Local:` 为准）。

### 4.4 端到端全链路验证（BFF 层汇总）

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
| `/api/analyze-resume` | 200 | `success=true`、`keywords` 非空、`score` 0–100、`meta.aiMode`/`meta.degraded` |
| `/api/match-job` | 200 | `match_score` 0–100、`level` 四级枚举、`hits`/`gaps` 数组、`breakdown`、`meta` |
| `/api/optimize-resume` | 200 | `summary`、`suggestions`/`missing_keywords` 数组、`meta` |
| `/api/radar` | 200 | `dimensions` 长度 5（降级时由规则层推导，非空），每项 `score` 0–100、`meta` |
| `/api/history` | 200 | `records` 含 `analysis`/`match`/`optimization`/`radar` 四类 |

> **契约字段提醒**：四个业务接口现已统一返回 `success` 与 `meta`（含 `timings{bff,java,python,llm,total}`、`degraded`、`aiMode`）。LLM 不可用时接口返回 `200` + 规则层结果，并以 `meta.degraded=true` / `meta.aiMode=rule` 标记，前端 `DegradedBanner` 会据此提示「规则引擎」模式。

> **字段契约提醒**：`/api/radar`（BFF 与 Java 一致）使用 `resume` / `jd` 字段；其余三接口使用 `resume_text` / `job_description`。这是**前端已对齐的既定契约**，非缺陷。

### 4.5 数据持久化验证（SQLite）

**预期结果**：BFF 首次请求后会生成 `bff/data/careerlens.db`（容器内为 `/app/data/careerlens.db`），并伴随 `-wal` / `-shm` 临时文件。
**验证标准**：`/api/history` 能返回历史记录；重启 BFF 后记录仍在；`docker-compose` 场景下 `bff-data` 卷保留数据。
> `.db` / `.db-wal` / `.db-shm` 均已在 `.gitignore` 中忽略，不应入库。

### 4.6 Docker Compose 部署验证

#### 阶段 1：配置校验 — 已实测通过

```powershell
cd careerlens-ai
docker compose config
```

**实测结果**：✅ 通过（exit 0），四服务 `python-service` / `java-service` / `bff` / `frontend` 渲染正常。

#### 阶段 2：完整构建启动 — 本次环境受限未通过

```powershell
docker compose up -d --build
docker compose ps            # 四服务均应为 healthy
```

**实测结果**：❌ 失败。错误为 `registry-1.docker.io: no such host` / `dial tcp ... connectex: 连接尝试失败`。
**根因**：当前环境可解析 DNS，但**到 Docker Hub 的网络不可达**，本地**无任何基础镜像缓存**（`docker pull hello-world` 同样失败）。**属环境网络限制，非 compose / Dockerfile 配置缺陷**（`docker compose config` 已证明配置合法）。

**在具备 Docker Hub 访问能力的环境中，预期验证标准**：

1. `docker compose ps` 显示四个容器 `healthy`；
2. 浏览器访问 `http://localhost:5173` 可正常使用四功能；
3. 反代生效：前端 `/api/*` 请求正确转发至 `bff:3000`；
4. `docker compose down` 后再 `up`，历史记录仍在（卷持久化）。

### 4.7 部署与回滚

**部署（首次 / 更新）**：

```powershell
git pull
docker compose up -d --build
docker compose ps          # 确认四服务 healthy
```

**回滚（容器场景）**：

```powershell
# 1) 切回上一个可用提交
git log --oneline -5
git checkout <上一个可用 commit>
# 2) 重新构建并启动
docker compose up -d --build
```

**回滚（本地开发场景）**：四端相互独立，可按层回退对应目录的代码并重启该服务，无需整体回滚；数据库为单文件 SQLite，回滚前建议备份 `bff/data/careerlens.db`。

> 说明：上述部署 / 回滚命令为**标准化流程**；其完整容器态验证因 4.6 阶段 2 的环境网络限制未能实跑，已在缺口 5.1-1 标注。

---

## 5. 已知缺口与后续优化方向

> 本节如实披露当前未完成 / 未实现 / 未验证的部分，供后续迭代排期。

### 5.1 已知缺口

1. **Docker Compose 完整启动未在本环境验证通过**：`docker compose config` 通过，但 `up --build` 因 Docker Hub 网络不可达失败。**代码与编排配置本身无已知缺陷**，需在可访问镜像仓库的环境复验。
2. **README 端口与启动命令过时**：`README.md` 表格仍写 bff=8080 / backend=8081，实际为 bff=3000 / java-service=8080；且 python 启动命令写的是 `uvicorn app.main:app`（实际入口为根目录 `main.py`）。**待修正**。
3. **LLM 降级语义不体现在状态码**：Python 四接口在 LLM 失败时返回 `200` + 降级结果，与 Java 层下游失败返回 `500` 的契约不一致。调用方需结合 `llm_enabled` 与响应内容判断是否走了真实 LLM。
4. **`backend/` 目录为骨架残留**：存在一个仅含 `HealthController` / `ServicePlaceholder` 的旧 Java 模块，未参与实际链路，属历史遗留，建议清理或明确其用途。
5. **SQLite 并发能力有限**：better-sqlite3 为同步单写者模型，高并发写场景会成为瓶颈；当前仅适用于单实例 / 低并发。
6. **无鉴权与限流**：所有接口开放，缺少 API Key / JWT 鉴权、速率限制与配额控制，不适合直接暴露公网。
7. **LLM 调用无重试与降级缓存**：仅实现本地字典兜底，未实现指数退避重试、结果缓存与熔断。
8. **历史记录无分页游标**：`/api/history` 仅支持 `limit`，无 offset / cursor 分页，大数据量下体验受限。
9. **测试未覆盖真实链路集成**：四端测试均为离线 mock；缺少 `docker compose` 级别的端到端集成测试（真实 LLM 需 Key，故默认不纳入 CI）。
10. **未配置日志聚合与监控**：仅有 docker json-file 日志（10m×3 轮转），无集中式日志、指标与告警。

### 5.2 后续优化方向

- **短期**：在可联网环境补跑 `docker compose up --build` 复验；修正 README 端口/命令；为 `/api/history` 增加分页；统一 LLM 降级的状态码语义（如引入 `degraded` 标记）。
  > 进展：Java 层下游失败仍返回 `500`，但 Python 四接口已在成功响应体内通过 `meta.degraded` / `meta.aiMode` 统一暴露降级语义，前端 `DegradedBanner` 可据此提示；状态码层面的统一仍待后续。
- **中期**：引入统一鉴权（网关 / BFF 中间件）；LLM 调用增加重试、超时降级与结果缓存；SQLite 迁移评估（PostgreSQL）。
- **长期**：接入可观测性（OpenTelemetry + Prometheus + 日志聚合）；补齐 CI 的端到端集成测试；清理骨架残留模块。

---

## 6. 交付物清单

| 类别 | 文件 | 状态 |
| --- | --- | --- |
| 容器编排 | `docker-compose.yml`、四服务 `Dockerfile`、`frontend/nginx.conf`、`.dockerignore` | 已完成（config 通过；up 受环境限制未验证） |
| Python 测试 | `python-service/tests/test_api.py`、`pytest.ini`、`requirements-dev.txt` | 已完成（**21 通过**） |
| BFF 测试 | `bff/tests/api.test.ts`、`bff/vitest.config.ts`、`bff/package.json#test` | 已完成（**19 通过**） |
| Java 测试 | `java-service/src/test/java/com/careerlens/controller/CareerControllerTest.java`、`pom.xml` | 已完成（**10 通过**） |
| 前端测试 | `frontend/src/{stores,components,api}/*.spec.ts` | 已完成（**30 通过**） |
| CI | `.github/workflows/ci.yml`（Python/BFF/Java/前端四作业） | 已完成 |
| 文档 | `DELIVERY.md`、`AI_LOG.md`、`README.md` | 已完成（README 待修订，见 5.1-2） |
