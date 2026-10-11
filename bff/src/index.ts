// ==================== BFF 启动入口 ====================
// 应用本体（路由、Java 转发、契约 meta 组装、SQLite 持久化）全部定义在 ./app.ts，
// 本文件仅负责在指定端口启动，保持「可测试的 app」与「可运行的进程」职责分离。
import { app } from './app.js'

const port = Number(process.env.PORT) || 3000

app.listen(port, () => {
  console.log(`BFF listening on http://localhost:${port}`)
})
