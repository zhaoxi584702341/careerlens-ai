# CareerLens AI — AI 协作会话日志（AI_LOG）

> 本文档按时间顺序归档本任务执行过程中与 AI 助手的完整交互：用户提问、AI 回复要点、关键决策的沟通过程与产出物。
>
> - 归档范围：本次任务会话（简历多模块复用 → LLM 降级排查 → main 分支提交推送 → 交付物核查与补齐）。
> - 记录原则：**只记录实际发生过、可追溯的交互**；未在本会话中确证的更早历史不作补写。
> - 配套文档：`DELIVERY.md`（交付说明）、`README.md`（快速上手）。
> - 会话语言：中文。

---

## 目录

- [会话 1：简历「一次上传、四模块复用」功能实现](#会话-1)
- [会话 2：LLM 服务不可用自动降级的排查请求](#会话-2)
- [会话 3：代码提交到 main 分支](#会话-3)
- [会话 4：交付物提交 + DELIVERY.md 完善](#会话-4)
- [会话 5：AI_LOG.md 会话归档](#会话-5)
- [附录 A：关键决策汇总](#附录a)
- [附录 B：验证记录与命令](#附录b)

---

<a id="会话-1"></a>
## 会话 1：简历「一次上传、四模块复用」功能实现

### 1.1 用户提问（原文）

> 在当前包含四个模块的简历系统中，实现简历内容一次上传、全页面复用的功能。具体要求如下：
> 1. 设计统一的简历内容上传入口…
> 2. 建立全局简历数据存储机制…
> 3. 确保其余三个模块页面能够自动读取并复用…
> 4. 增加数据同步机制…
> 5. 保留上传状态标识…
> 6. 实现异常兼容处理…
> 7. 完成功能后进行全链路测试…

### 1.2 AI 回复与执行要点

| 序号 | 动作 | 产出 |
| --- | --- | --- |
| 1 | 新建全局 Pinia Store | `frontend/src/stores/resume.ts`：`resumeText`/`source` 状态；`hasResume`/`charCount` 派生；`setResume`/`updateText`/`clear`/`applyExternal`/`initSync` 动作 |
| 2 | localStorage 持久化 + 跨标签页同步 | `STORAGE_KEY = 'careerlens.resume.v1'`；`storage` 事件监听实现多标签页同步 |
| 3 | 新建全局状态条组件 | `frontend/src/components/UploadStatusBar.vue`：已上传显示文件名/格式/字符数/更新时间；未上传显示提示与快捷上传入口 |
| 4 | 改造上传页 | `UploadResumeView.vue`：解析结果写入 store |
| 5 | 改造其余三视图 | `JobMatchView` / `ResumeOptimizeView` / `RadarView`：简历字段与 store 双向绑定（`computed` get/set 调 `store.updateText`） |
| 6 | 全局挂载 | `AppLayout.vue` 挂载 `UploadStatusBar` |
| 7 | 补充单测 + 构建验证 | 新增 `frontend/src/stores/resume.spec.ts`；`npm run build` 与 `vitest` 通过 |

### 1.3 关键决策与沟通

- **决策：用 Pinia + localStorage 而非状态提升到 App 根组件。** 理由：四个模块为独立路由页面，Store 天然跨页面共享，且无需逐层透传 props。
- **决策：跨标签页同步采用浏览器原生 `storage` 事件。** 理由：零依赖，满足「多标签页打开同一系统时数据一致」的诉求。
- **决策：上传页解析后写入 Store，统一数据源。** 其余三页改为「只读复用 + 可编辑回写」，避免各自维护副本产生不一致。

### 1.4 验证结果

- 单测：`frontend/` 共 30 用例通过（`api.spec.ts` / `components.spec.ts` / `resume.spec.ts`）。
- 构建：`npm run build` 成功。
- 浏览器：四页面均能读取到同一份简历内容，`UploadStatusBar` 状态正确。

---

<a id="会话-2"></a>
## 会话 2：LLM 服务不可用自动降级的排查请求

### 2.1 用户提问（原文）

> 请对当前系统中 LLM 服务不可用并自动降级为规则引擎结果的异常情况进行全面排查与根因分析：
> 1. 首先验证当前系统状态，确认 LLM 服务的连接状态、接口响应情况、认证配置是否正常
> 2. 排查可能的故障点：包括但不限于 LLM 服务端可用性、网络连通性、API 密钥有效性、请求配额限制、超时配置、依赖组件状态
> 3. 确认降级逻辑的触发条件与执行链路，验证当前输出的规则引擎结果符合「可复现、无编造」的质量标准
> 4. 输出完整的故障根因分析报告，同时提供临时规避方案与长期预防措施，确保 LLM 服务恢复后可正常切换回原服务链路
> 5. 完成修复后进行全链路验证，确认 LLM 服务调用恢复正常且无二次异常触发降级逻辑

> 说明：该请求在会话中被用户连续发送多次（同一诉求重复提交）。后续被「提交到 main 分支」的新请求覆盖优先级，本会话内**未正式展开**成完整报告。

### 2.2 期间实际发现并修复的问题

排查过程中定位到 Python 服务的一个**启动即崩溃**缺陷：

- **现象**：`python main.py` 抛出 `NameError: name 'logger' is not defined`，服务无法启动。
- **根因**：`python-service/main.py` 中 `logger` 被 LLM 初始化与四个接口的降级分支**共 8 处引用**，但模块内从未定义该变量。
- **修复**：在 `load_dotenv()` 之后新增：

```python
import logging

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("careerlens.python")
```

- **验证**：服务成功启动，日志输出 `LLM client initialized and verified, model=gpt-5.6-sol, base_url=https://re.94xy.cn/v1`、`Uvicorn running on http://0.0.0.0:8000`。
- **LLM 连通性**：`https://re.94xy.cn/v1/models` 返回 `HTTP/1.1 200 OK`，确认链路未降级。

### 2.3 降级链路的既有设计（供根因分析参考）

`python-service/main.py` 四个接口在 LLM 调用失败时统一走「**HTTP 200 + 本地规则结果 + 警告 message**」的降级策略（不返回 500），例如：

- `/api/analyze`：降级为本地字典 `extract_skills()` 命中结果，`score` 置 0；
- `/api/match`：降级为技能集合交并差（`matched_skills` / `missing_skills`）；
- `/api/optimize`：降级为空建议 `{summary:"", suggestions:[], missing_keywords:[]}`；
- `/api/radar`：降级为空维度 `{dimensions:[]}`。

超时保护：`LLM_TIMEOUT_SECONDS = 30`。

---

<a id="会话-3"></a>
## 会话 3：代码提交到 main 分支

### 3.1 用户提问（原文）

> 请执行以下操作将代码提交到 main 分支：
> 1. 首先切换到本地 main 分支，确保本地 main 分支与远程仓库最新代码保持同步
> 2. 使用 git add 命令添加所有需要提交的变更文件，明确排除 `.env.example` 文件
> 3. 编写清晰、规范的提交信息
> 4. 执行 git commit 完成本地提交
> 5. 将本地 main 分支的提交推送到远程仓库的 main 分支
> 6. 推送完成后验证远程仓库的提交记录，确认 `.env.example` 文件未被本次提交修改或覆盖

### 3.2 澄清式提问与用户决策（AskUserQuestion）

| 问题 | 选项 | 用户选择 |
| --- | --- | --- |
| 远程仓库不可达（SSH 22 端口被拒）时如何处理？ | 仅本地提交 / 强行重试 / 换协议 | **只做本地 commit，push 暂缓** |
| 本次提交范围 | 仅部分变更 / 全部变更 | **全部变更（除 .env.example）** |
| 本地 main 切换被工作区改动阻塞，如何推进？ | 放弃改动 / 停进程后切分支提交 | **停进程后切分支提交（推荐）** |

### 3.3 执行过程与遇到的障碍

| 障碍 | 处理 |
| --- | --- |
| `git rev-parse --show-toplevel` 在 `boss-demo` 根目录失败 | 确认仓库根实为 `careerlens-ai/` |
| PowerShell 中 `stash@{0}` 被解析为多个参数 | 改用单引号 `'stash@{0}'` |
| `git checkout main` 被拒（`core.autocrlf=true` + dev 服务持续改写文件导致 EOL churn） | 先 `git stash push -u`，再停进程，再切分支 |
| `git stash pop` 被 untracked 文件阻塞 | 清理 untracked → `git checkout -- .` → 重新 `stash pop` 并 drop |
| `git checkout main` 仍被拒 | 改用 `git checkout -m main`，产生 19 处冲突 |
| 19 处合并冲突 | `git diff --name-only --diff-filter=U` 后统一 `git checkout develop -- <file>` 取本地内容，冲突归零 |
| PowerShell 不支持 heredoc | 提交信息写入临时文件后用 `git commit -F` 提交 |
| `.env.example` 排除校验 | `git restore --staged --worktree` + `git status`/`git diff` 双重确认无变化、不在 staged 列表 |

### 3.4 提交结果

| 提交 | 说明 | 文件数 |
| --- | --- | --- |
| `d8d9f08` | `feat: 完成 CareerLens AI 全链路功能与简历多模块复用` | 111 |
| `e6e041e` | `fix(python): 修复 main.py 缺少 logger 定义导致的启动崩溃` | 1 |

- 验证：`git show --stat --name-only` 全量过滤 `env.example`，仅命中提交信息文字，**文件本身未进入任何提交**。

### 3.5 推送与远程切换

- 首次 `git push origin main` 失败：`ssh: connect to host github.com port 22: Connection refused`。
- 用户决策：**将 remote 换成 HTTPS**。
- 执行：`git remote set-url origin https://github.com/zhaoxi584702341/careerlens-ai.git`。
- 推送成功：`1194e4f..e6e041e  main -> main`。
- 远程验证：
  - `git log origin/main --oneline -5` 顶端为 `e6e041e`，与本地 `HEAD` 哈希完全一致（`e6e041ef340faada764da327fc1a43b44b756d87`）；
  - `git diff --name-only 33b9ec8..e6e041e | grep env.example` 无输出；
  - `git status --short python-service/.env.example` 无输出。
- **结论：`.env.example` 未被本次提交修改或覆盖。**

---

<a id="会话-4"></a>
## 会话 4：交付物提交 + DELIVERY.md 完善

### 4.1 用户提问（原文）

> 2. 提交可运行代码、测试、Docker/Compose 与 CI/CD 配置，并在 `DELIVERY.md` 写明实际验证过的启动、测试、部署/回滚、架构取舍和已知缺口。
> 3. 与 AI 的会话历史，记录到 `AI_LOG.md`

### 4.2 AI 核查发现（重要）

对仓库进行实证核查后，发现 **`DELIVERY.md` 存在与代码库严重不符的描述**：

**文档声称已完成、但 main 分支上实际不存在的交付物**：

| 文档声称 | main 分支实际状态 |
| --- | --- |
| `docker-compose.yml`、四服务 `Dockerfile` | **不存在**（`Test-Path` 全部为 False） |
| `.dockerignore` | **不存在** |
| `frontend/nginx.conf` | **不存在** |
| `java-service/pom.xml` | **不存在**（Java 服务在 main 上没有构建文件） |
| `python-service/pytest.ini` | **不存在** |
| `bff/vitest.config.ts`、`bff/package.json#test` | **不存在**（`package.json` 无 `test` 脚本、无 vitest 依赖） |
| `AI_LOG.md` | **不存在**（本次任务创建） |

**更严重的运行时缺陷（实测确认）**：

- `bff/src/app.ts` 第 13 行 `import {...} from './db.js'`，但 main 分支的 `bff/src/` 下**只有 `app.ts` 与 `index.ts`，没有 `db.ts`**。
- 实测 `npm run type-check` 输出：`src/app.ts(13,8): error TS2307: Cannot find module './db.js'`。
- **根因（已查明，修正先前的误判）**：这些交付物**并未丢失**，而是**位于 `develop` 分支**。`main` 与 `develop` 是从共同祖先 `33b9ec8` 分叉出的**两条独立历史**：
  - `develop`（`94a8b9d`）：包含全部交付物（`db.ts`、`pom.xml`、`docker-compose.yml`、各 `Dockerfile`、`nginx.conf`、`pytest.ini`、`vitest.config.ts`、`DELIVERY.md`、`AI_LOG.md`）；
  - `main`（`e6e041e`）：历史为 `eca62a3 → 1194e4f → 33b9ec8 → d8d9f08 → e6e041e`，**绕过了 develop 上承载交付物的提交**。
  - 因此先前把 `db.ts` 描述为「仅存在于孤儿提交 `d68e8ba`」是不准确的——它只是**不在 main 的祖先链上**，在 develop 上是正常历史。
- 同时 `bff/package.json` 在 main 上缺少 `better-sqlite3`、`dotenv`、`supertest`、`vitest` 等依赖与 `test` 脚本。
- **结论：main 上的 BFF 无法构建、无法运行、无法测试**（交付物都在 develop）。
- 附带问题：远程仓库跟踪了 `bff/data/careerlens.db-shm`、`careerlens.db-wal` 等 SQLite 运行时文件（应被忽略）。

### 4.3 澄清式提问与用户决策（AskUserQuestion）

| 问题 | 用户选择 |
| --- | --- |
| `AI_LOG.md` 覆盖哪些内容？ | **本次可见会话 + 已有成果**（不编造更早会话细节） |
| 文档要求「实际验证过」，但多项交付物缺失且环境受限，如何处理？ | **先补齐缺失交付物再验证** |
| 缺失交付物如何补齐？ | **从 develop 恢复**（而非整体 merge，避免引入 develop 的 app/ 重构与 main 的 components 冲突） |
| Docker 验证到什么程度？ | **完整跑 `compose up`** |
| 是否提交并推送？ | **commit + push** |
| Python 测试与实现契约冲突（测试期望 500/string，实现为 200/bool）如何处理？ | **改测试对齐实现** |

### 4.4 环境探测结果

| 工具 | 结果 |
| --- | --- |
| `mvn` | 可用 → `D:\apache-maven-3.10.0\bin\mvn.cmd` |
| `java` | 可用 → **Java 27**（`build 27+35-2325`） |
| `docker` | 可用 → `DockerDesktop\resources\bin\docker.exe` |
| `docker compose` | 可用 → **v5.5.1** |
| `node` / `npm` | 可用 |
| `python` | 可用 → `C:\Python313\python.exe` |

> 与先前「本机缺 Maven」的判断不一致：实测 Maven 与 Docker 均可用，因此 Java 测试与 Docker 编排均**具备实际验证条件**。

### 4.5 修复执行与结果

按用户决策「从 develop 恢复」精确取回 19 个交付物文件，未整体 merge：

```
git checkout develop -- <path>   # .dockerignore / bff/.dockerignore / bff/Dockerfile / bff/src/db.ts
                                 # bff/vitest.config.ts / bff/package.json / bff/package-lock.json
                                 # docker-compose.yml / frontend/.dockerignore / frontend/Dockerfile
                                 # frontend/nginx.conf / java-service/.dockerignore / java-service/.gitignore
                                 # java-service/Dockerfile / java-service/pom.xml
                                 # java-service/src/main/java/com/careerlens/JavaServiceApplication.java
                                 # python-service/.dockerignore / python-service/Dockerfile / python-service/pytest.ini
```

同时补齐两处依赖缺口：

- `python-service/requirements.txt` 新增 `openai==1.54.4`（`main.py` 第 21 行 `from openai import OpenAI` 需要）。
- `python-service/main.py` 修正 `/health` 返回类型注解 `dict[str, str]` → `dict[str, Any]`（原注解与 `llm_enabled: bool` 值冲突，导致 FastAPI `ResponseValidationError`）。
- `python-service/tests/test_api.py` 按用户决策「改测试对齐实现」，修正 6 处断言（3 处 LLM 失败由 500 → 200；缺失字段由 422 → 200 + "不能为空"；补 `llm_enabled` 布尔断言）。

### 4.6 逐项实跑验证结果

| 验证项 | 命令 | 实测结果 |
| --- | --- | --- |
| BFF 类型检查 | `npm run type-check`（bff） | ✅ 通过（exit 0） |
| BFF 测试 | `npm test`（bff） | ✅ **18 passed**（1 file） |
| Python 测试 | `.\.venv\Scripts\python.exe -m pytest` | ✅ **19 passed** |
| Java 测试 | `mvn -B test` | ✅ **10 passed**，BUILD SUCCESS |
| 前端测试 | `npm test` | ✅ **30 passed**（3 files） |
| 前端构建 | `npm run build` | ✅ 成功（约 8.2s） |
| Compose 配置校验 | `docker compose config` | ✅ 通过，四服务渲染正常 |
| Compose 完整构建启动 | `docker compose up -d --build` | ❌ **失败**：`registry-1.docker.io: no such host`，Docker Hub 网络不可达，本地无镜像缓存（`docker pull hello-world` 同样失败）。**属环境限制，非配置缺陷** |

**据实测结果重写 `DELIVERY.md`**：将「Compose 完整启动」明确标注为环境受限未通过，其余项据真实输出记录；测试口径更新为 Python 19 / BFF 18 / Java 10 / 前端 30。

### 4.7 遗留待办

1. 清理 `bff/data/*.db-shm` / `*.db-wal` 的 git 跟踪，并更新 `.gitignore`（本次核查确认 `.gitignore` 已含忽略规则，仍需 `git rm --cached` 已跟踪的运行时文件）；
2. 将本轮安全可交付的变更 commit 并 push 到 `origin/main`。

---

<a id="会话-5"></a>
## 会话 5：AI_LOG.md 会话归档

### 5.1 用户提问（原文）

> 将本次任务执行过程中与AI助手的完整交互会话历史，按时间顺序整理并记录到 `AI_LOG.md` 文档中，包含所有提问内容、AI回复内容、关键决策的沟通过程，确保会话历史完整可追溯。

### 5.2 AI 回复

即本文档。按时间顺序归档会话 1–5 的用户提问、AI 执行要点、关键决策与验证记录；对未确证的更早历史不作补写，对尚未完成的交付项如实标注状态。

---

<a id="附录a"></a>
## 附录 A：关键决策汇总

| # | 决策 | 依据 |
| --- | --- | --- |
| 1 | 用 Pinia Store + localStorage 实现简历四模块复用 | 跨路由页面共享状态，避免 props 逐层透传 |
| 2 | 跨标签页同步用原生 `storage` 事件 | 零依赖，满足多标签页数据一致 |
| 3 | LLM 失败时返回 HTTP 200 + 降级结果 + 警告 | 前端可优雅展示降级态，不因单点失败整页报错 |
| 4 | 远程不可达时先本地 commit、push 暂缓 | 用户决策，避免阻塞本地进度 |
| 5 | 提交范围＝全部变更（除 `.env.example`） | 用户决策 |
| 6 | 切分支前先停进程（先关后开） | `core.autocrlf=true` + dev 服务改写文件导致 EOL churn |
| 7 | 冲突统一取 develop（本地）版本 | 用户意图即提交本地内容，避免丢失 |
| 8 | remote 由 SSH 改 HTTPS | SSH 22 端口被拒；HTTPS 443 可达 |
| 9 | 文档只写「实际验证过」的内容 | 用户明确要求，且发现原文档存在不实描述 |
| 10 | 先补齐缺失交付物再验证 | 用户决策 |
| 11 | 交付物「从 develop 恢复」而非整体 merge | 避免引入 develop 的 app/ 重构与 main 的 components 冲突 |
| 12 | Python 测试「改测试对齐实现」 | 实现对（200 + 降级），测试断言为旧契约（500） |
| 13 | Docker 完整跑 `compose up` 验证 | 用户要求尽可能完整验证，最终受网络限制止步于 config |

---

<a id="附录b"></a>
## 附录 B：验证记录与命令

### B.1 本次会话已实际执行并取得结果的验证

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| Python 服务启动 | `.\.venv\Scripts\python.exe main.py` | 启动成功，`Uvicorn running on http://0.0.0.0:8000` |
| LLM 连通性 | 探测 `models.list()` | `HTTP/1.1 200 OK`，model=`gpt-5.6-sol` |
| 前端单测 | `npm test`（frontend） | 30 passed（3 files） |
| 前端构建 | `npm run build` | 成功（1138 modules） |
| BFF 类型检查 | `npm run type-check` | **失败**：`Cannot find module './db.js'`（已定位根因） |
| 远程推送 | `git push origin main` | 成功：`1194e4f..e6e041e` |
| 远程一致性 | `git rev-parse HEAD` vs `origin/main` | 两者同为 `e6e041ef340faada764da327fc1a43b44b756d87` |
| `.env.example` 排除 | `git diff --name-only 33b9ec8..e6e041e` | 无匹配输出 |

### B.1.1 补齐交付物后的复验结果（会话 4 后续）

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| BFF 类型检查 | `npm run type-check`（bff） | ✅ 通过（exit 0） |
| BFF 测试 | `npm test`（bff） | ✅ 18 passed（1 file） |
| Python 测试 | `.\.venv\Scripts\python.exe -m pytest` | ✅ 19 passed |
| Java 测试 | `mvn -B test` | ✅ 10 passed，BUILD SUCCESS |
| 前端测试 | `npm test`（frontend） | ✅ 30 passed（3 files） |
| 前端构建 | `npm run build` | ✅ 成功（约 8.2s） |
| Compose 配置校验 | `docker compose config` | ✅ 通过（四服务渲染正常） |
| Compose 完整启动 | `docker compose up -d --build` | ❌ 失败：Docker Hub 网络不可达（环境限制） |

### B.3 契约贯通改造（会话 5）

**背景**：核查发现 Python 侧存在「契约与实现脱节」与「`rules.py` 孤儿模块」两处落差——`main.py` 未调用 `rules.py`，且未产出契约声明的 `meta`/`level`/`hits`/`gaps`/`qualityIssues`/`skills` 字段。经与用户确认，采纳「接线 `rules.py` + 补齐契约字段」方案。

**Python 侧改动**（`python-service/main.py`、`tests/test_api.py`）：
- 引入 `rules.py` 的 `compute_match`/`extract_skill_hits`/`detect_quality_issues`/`normalize_text`/`split_sections`/`build_learning_path` 等；
- 新增 `build_meta()` 统一产出 `meta{timings{...},degraded,aiMode}`，`AI_MODE` 环境变量控制 `llm|hybrid|rule`；
- 四接口（analyze/match/optimize/radar）补齐契约字段；LLM 失败降级时 `meta.degraded=true`、`meta.aiMode=rule`，雷达降级由规则层推导五维度（非空）；
- 请求模型同时接受下划线与驼峰字段（`resume_text`/`resumeText`）。

**BFF 侧改动**（`bff/src/app.ts`、`tests/api.test.ts`）：
- 新增 `withBffMeta()`：保留下游 `meta`，追加 BFF 段耗时并重算 `total`，缺失时按降级兜底；
- 四个接口统一透传 `success`/`meta`（match 另透传 `level`/`breakdown`/`hits`/`gaps`），catch 分支统一补 `success: false`。

**复验结果**：

| 验证项 | 命令 | 结果 |
| --- | --- | --- |
| Python 测试 | `.\.venv\Scripts\python.exe -m pytest -q` | ✅ 21 passed |
| BFF 类型检查 | `npm run type-check` | ✅ 通过（exit 0） |
| BFF 测试 | `npm test` | ✅ 19 passed（1 file） |
| 前端测试 | `npm test -- --run` | ✅ 30 passed（3 files） |
| 前端构建 | `npm run build` | ✅ 成功（约 8.4s） |
| 契约校验 | `.\.venv\Scripts\python.exe ..\scripts\validate-contracts.py` | ✅ PASS=19 FAIL=0 |

### B.2 环境探测

| 工具 | 版本/路径 |
| --- | --- |
| Java | 27（`27+35-2325`） |
| Maven | `D:\apache-maven-3.10.0\bin\mvn.cmd` |
| Docker Compose | v5.5.1 |
| Node / npm | `C:\Program Files\nodejs\` |
| Python | `C:\Python313\python.exe` |

---

*本文档由 AI 助手依据本会话实际交互过程整理，未确证内容不作补写。*
