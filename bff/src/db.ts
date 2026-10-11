import 'dotenv/config'
import Database from 'better-sqlite3'
import type { Database as DatabaseType } from 'better-sqlite3'
import { mkdirSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

// ===== 数据存储路径：bff/data/careerlens.db =====
// 以当前文件（bff/src/db.ts）为基准定位到 bff 根目录，避免受启动目录影响
const __dirname = dirname(fileURLToPath(import.meta.url))
const bffRoot = resolve(__dirname, '..')
const dataDir = resolve(bffRoot, 'data')

// 数据库文件路径，支持通过环境变量覆盖
const dbPath = process.env.DB_PATH
  ? resolve(process.env.DB_PATH)
  : resolve(dataDir, 'careerlens.db')

// 确保数据目录存在（首次运行自动创建 bff/data/）
if (!existsSync(dataDir)) {
  mkdirSync(dataDir, { recursive: true })
}

// ===== 数据库连接管理（单例） =====
export const db: DatabaseType = new Database(dbPath)

// 开启 WAL 模式提升并发读写性能，并打开外键约束
db.pragma('journal_mode = WAL')
db.pragma('foreign_keys = ON')

// ===== 数据表初始化 =====
// 表结构字段与下方封装方法的参数严格对应
db.exec(`
  -- 简历文本表
  CREATE TABLE IF NOT EXISTS resumes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_text TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  );

  -- 岗位描述表
  CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_description TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
  );

  -- 简历分析结果表（关联简历）
  CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resume_id) REFERENCES resumes(id)
  );

  -- 岗位匹配结果表（关联简历与岗位）
  CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resume_id) REFERENCES resumes(id),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
  );

  -- 简历优化结果表（关联简历与岗位）
  CREATE TABLE IF NOT EXISTS optimizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resume_id) REFERENCES resumes(id),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
  );

  -- 雷达评估结果表（关联简历与岗位）
  CREATE TABLE IF NOT EXISTS radars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER NOT NULL,
    job_id INTEGER NOT NULL,
    result_json TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resume_id) REFERENCES resumes(id),
    FOREIGN KEY (job_id) REFERENCES jobs(id)
  );

  -- 常用查询索引
  CREATE INDEX IF NOT EXISTS idx_analyses_resume ON analyses(resume_id);
  CREATE INDEX IF NOT EXISTS idx_matches_resume ON matches(resume_id);
  CREATE INDEX IF NOT EXISTS idx_optimizations_resume ON optimizations(resume_id);
  CREATE INDEX IF NOT EXISTS idx_radars_resume ON radars(resume_id);
`)

// ===== 通用操作方法封装 =====

/**
 * 保存简历文本数据，返回生成的简历 ID
 */
export function saveResume(resume_text: string): number {
  const stmt = db.prepare('INSERT INTO resumes (resume_text) VALUES (?)')
  const info = stmt.run(resume_text)
  return Number(info.lastInsertRowid)
}

/**
 * 保存岗位描述数据，返回生成的岗位 ID
 */
export function saveJob(job_description: string): number {
  const stmt = db.prepare('INSERT INTO jobs (job_description) VALUES (?)')
  const info = stmt.run(job_description)
  return Number(info.lastInsertRowid)
}

/**
 * 保存简历分析结果，关联对应简历 ID
 */
export function saveAnalysis(resume_id: number, result_json: string): number {
  const stmt = db.prepare('INSERT INTO analyses (resume_id, result_json) VALUES (?, ?)')
  const info = stmt.run(resume_id, result_json)
  return Number(info.lastInsertRowid)
}

/**
 * 保存岗位匹配结果，关联对应简历 ID 和岗位 ID
 */
export function saveMatch(resume_id: number, job_id: number, result_json: string): number {
  const stmt = db.prepare('INSERT INTO matches (resume_id, job_id, result_json) VALUES (?, ?, ?)')
  const info = stmt.run(resume_id, job_id, result_json)
  return Number(info.lastInsertRowid)
}

/**
 * 保存简历优化结果，关联对应简历 ID 和岗位 ID
 */
export function saveOptimization(resume_id: number, job_id: number, result_json: string): number {
  const stmt = db.prepare(
    'INSERT INTO optimizations (resume_id, job_id, result_json) VALUES (?, ?, ?)',
  )
  const info = stmt.run(resume_id, job_id, result_json)
  return Number(info.lastInsertRowid)
}

/**
 * 保存雷达评估结果，关联对应简历 ID 和岗位 ID
 */
export function saveRadar(resume_id: number, job_id: number, result_json: string): number {
  const stmt = db.prepare('INSERT INTO radars (resume_id, job_id, result_json) VALUES (?, ?, ?)')
  const info = stmt.run(resume_id, job_id, result_json)
  return Number(info.lastInsertRowid)
}

// 历史记录中单条记录的返回结构
export interface HistoryRecord {
  id: number
  type: 'analysis' | 'match' | 'optimization' | 'radar'
  resume_id: number
  job_id: number | null
  resume_text: string
  job_description: string | null
  result: unknown
  created_at: string
}

// 安全解析 JSON，避免脏数据导致接口异常
function safeParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

/**
 * 查询最近的 N 条历史记录，统一返回四类功能的记录集合
 * 按创建时间倒序，{ limit } 条
 */
export function getRecentRecords(limit = 20): HistoryRecord[] {
  const safeLimit = Number.isFinite(limit) && limit > 0 ? Math.floor(limit) : 20

  const sql = `
    SELECT id, 'analysis' AS type, resume_id, NULL AS job_id, result_json, created_at
      FROM analyses
    UNION ALL
    SELECT id, 'match' AS type, resume_id, job_id, result_json, created_at
      FROM matches
    UNION ALL
    SELECT id, 'optimization' AS type, resume_id, job_id, result_json, created_at
      FROM optimizations
    UNION ALL
    SELECT id, 'radar' AS type, resume_id, job_id, result_json, created_at
      FROM radars
    ORDER BY created_at DESC, id DESC
    LIMIT ?
  `

  const rows = db.prepare(sql).all(safeLimit) as {
    id: number
    type: HistoryRecord['type']
    resume_id: number
    job_id: number | null
    result_json: string
    created_at: string
  }[]

  const resumeStmt = db.prepare('SELECT resume_text FROM resumes WHERE id = ?')
  const jobStmt = db.prepare('SELECT job_description FROM jobs WHERE id = ?')

  return rows.map((row) => {
    const resume = resumeStmt.get(row.resume_id) as { resume_text: string } | undefined
    const job =
      row.job_id != null
        ? (jobStmt.get(row.job_id) as { job_description: string } | undefined)
        : undefined

    return {
      id: row.id,
      type: row.type,
      resume_id: row.resume_id,
      job_id: row.job_id,
      resume_text: resume?.resume_text ?? '',
      job_description: job?.job_description ?? null,
      result: safeParse(row.result_json),
      created_at: row.created_at,
    }
  })
}
