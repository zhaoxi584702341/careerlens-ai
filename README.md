# CareerLens AI

多服务架构的 AI 招聘/职业匹配项目，包含四个子项目：

| 子项目 | 技术栈 | 默认端口 | 说明 |
| --- | --- | --- | --- |
| frontend | Vue 3 + Vite + TypeScript | 5173 | 前端界面 |
| bff | Node.js + TypeScript (Express) | 3000 | 面向前端的后端聚合层 |
| java-service | Java 17 + Spring Boot (Maven) | 8080 | 业务编排与字段映射层 |
| python-service | Python + FastAPI | 8000 | AI 能力服务 |

## 启动方式

- frontend: `npm install && npm run dev`
- bff: `npm install && npm run dev`
- java-service: `mvn spring-boot:run`
- python-service: `pip install -r requirements.txt && uvicorn main:app --reload --port 8000`

## 一键启动（Docker Compose）

```bash
docker compose up -d --build
```

启动后访问 `http://localhost:5173`。
