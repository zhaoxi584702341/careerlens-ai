# CareerLens AI

多服务架构的 AI 招聘/职业匹配项目，包含四个子项目：

| 子项目 | 技术栈 | 默认端口 | 说明 |
| --- | --- | --- | --- |
| frontend | Vue 3 + Vite + TypeScript | 5173 | 前端界面 |
| bff | Node.js + TypeScript (Express) | 8080 | 面向前端的后端聚合层 |
| backend | Java 21 + Spring Boot (Maven) | 8081 | 核心业务后端 |
| python-service | Python + FastAPI | 8000 | AI 能力服务 |

## 启动方式

- frontend: `npm install && npm run dev`
- bff: `npm install && npm run dev`
- backend: `mvn spring-boot:run`
- python-service: `pip install -r requirements.txt && uvicorn app.main:app --reload --port 8000`
