/**
 * 简历文件解析工具。
 *
 * 职责：把用户拖拽/选择的简历文件（PDF / Word / 图片 / 纯文本）在浏览器本地
 * 解析为纯文本，供后续分析链路复用（不改变后端只接收 resume_text 的契约）。
 *
 * 支持格式：
 * - PDF      ：pdfjs-dist 提取文本层（保留分页分隔）
 * - DOCX     ：mammoth 提取纯文本
 * - 图片     ：tesseract.js 做 OCR（中英混合）
 * - 纯文本   ：FileReader 直接读取
 *
 * 统一约定：所有解析函数成功返回文本，失败抛出 Error（message 为可展示的中文提示）。
 */

/** 文件格式大类 */
export type ResumeFileKind = 'pdf' | 'word' | 'image' | 'text'

/** 单个文件的解析结果 */
export interface ParsedResume {
  /** 原始文件名 */
  name: string
  /** 解析出的纯文本 */
  text: string
  /** 命中的格式大类 */
  kind: ResumeFileKind
}

/** 允许上传的最大文件体积：10 MB（超出提示用户） */
export const MAX_FILE_SIZE = 10 * 1024 * 1024

/** 允许的文件扩展名 */
export const ACCEPTED_EXTENSIONS = ['.pdf', '.docx', '.doc', '.txt', '.md', '.png', '.jpg', '.jpeg', '.webp', '.bmp'] as const

/** 拖拽区域 accept 属性用（与 ACCEPTED_EXTENSIONS 对齐） */
export const ACCEPT_ATTR = ACCEPTED_EXTENSIONS.join(',')

/**
 * 根据文件名/ MIME 判定格式大类；无法识别返回 null。
 */
export function detectKind(file: File): ResumeFileKind | null {
  const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
  const type = file.type.toLowerCase()

  if (ext === '.pdf' || type === 'application/pdf') return 'pdf'
  if (ext === '.docx' || ext === '.doc' || type.includes('wordprocessingml') || type === 'application/msword') return 'word'
  if (type.startsWith('image/') || ['.png', '.jpg', '.jpeg', '.webp', '.bmp'].includes(ext)) return 'image'
  if (['.txt', '.md'].includes(ext) || type.startsWith('text/')) return 'text'
  return null
}

/**
 * 校验文件：返回错误提示文本；通过则返回 null。
 */
export function validateFile(file: File): string | null {
  if (file.size === 0) {
    return `文件「${file.name}」为空，请重新选择。`
  }
  if (file.size > MAX_FILE_SIZE) {
    return `文件「${file.name}」超过 10MB 上限，请压缩后重试。`
  }
  if (!detectKind(file)) {
    return `不支持的文件格式「${file.name}」，请上传 PDF / Word / 图片 / 文本文件。`
  }
  return null
}

/** 读取为纯文本（txt / md）。 */
function readAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(new Error('文本文件读取失败，请重试。'))
    reader.readAsText(file)
  })
}

/** 读取为 ArrayBuffer（pdf / docx）。 */
function readAsArrayBuffer(file: File): Promise<ArrayBuffer> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as ArrayBuffer)
    reader.onerror = () => reject(new Error('文件读取失败，请重试。'))
    reader.readAsArrayBuffer(file)
  })
}

/** 读取为 DataURL（图片 OCR）。 */
function readAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result ?? ''))
    reader.onerror = () => reject(new Error('图片读取失败，请重试。'))
    reader.readAsDataURL(file)
  })
}

/**
 * 解析 PDF 文本层。pdfjs 采用动态 import，避免拖累首屏体积。
 * 按页拼接，页与页之间留空行，尽量保留原有排版段落结构。
 */
async function parsePdf(file: File): Promise<string> {
  const pdfjs = await import('pdfjs-dist')
  // 指定 worker：走打包产物内的 worker 入口，避免跨域/路径问题
  const workerUrl = (await import('pdfjs-dist/build/pdf.worker.min.mjs?url')).default
  pdfjs.GlobalWorkerOptions.workerSrc = workerUrl

  const buffer = await readAsArrayBuffer(file)
  const loadingTask = pdfjs.getDocument({ data: new Uint8Array(buffer) })
  const doc = await loadingTask.promise
  try {
    const pages: string[] = []
    for (let i = 1; i <= doc.numPages; i++) {
      const page = await doc.getPage(i)
      const content = await page.getTextContent()
      // 依据 textContent 的换行标记还原行结构
      let line = ''
      const lines: string[] = []
      for (const item of content.items as Array<{ str?: string; hasEOL?: boolean }>) {
        const str = item.str ?? ''
        line += str
        if (item.hasEOL) {
          lines.push(line)
          line = ''
        }
      }
      if (line) lines.push(line)
      pages.push(lines.join('\n'))
    }
    return pages.join('\n\n')
  } finally {
    await loadingTask.destroy()
  }
}

/** 解析 Word（.docx）文本，mammoth 动态导入。 */
async function parseWord(file: File): Promise<string> {
  const mammoth = await import('mammoth')
  const buffer = await readAsArrayBuffer(file)
  const result = await mammoth.extractRawText({ arrayBuffer: buffer })
  return result.value ?? ''
}

/** 解析图片（OCR），tesseract.js 动态导入，识别中英混合文本。 */
async function parseImage(file: File): Promise<string> {
  const { recognize } = await import('tesseract.js')
  const dataUrl = await readAsDataURL(file)
  const { data } = await recognize(dataUrl, 'chi_sim+eng')
  return data.text ?? ''
}

/**
 * 统一入口：按格式解析文件为文本。
 * @throws Error 当格式不支持、文件非法或解析失败时，抛出可直接展示的中文提示。
 */
export async function parseResumeFile(file: File): Promise<ParsedResume> {
  const invalid = validateFile(file)
  if (invalid) throw new Error(invalid)

  const kind = detectKind(file) as ResumeFileKind

  try {
    let text = ''
    if (kind === 'pdf') text = await parsePdf(file)
    else if (kind === 'word') text = await parseWord(file)
    else if (kind === 'image') text = await parseImage(file)
    else text = await readAsText(file)

    if (!text.trim()) {
      throw new Error(
        kind === 'image'
          ? `未能从图片「${file.name}」中识别出文字，请换一张更清晰的图片或直接粘贴文本。`
          : `未能从文件「${file.name}」中提取到文本内容，请检查文件是否为扫描件（可改用图片 OCR）或直接粘贴文本。`,
      )
    }
    return { name: file.name, text, kind }
  } catch (error) {
    // 已是可展示提示则原样抛出，避免二次包裹
    if (error instanceof Error && error.message.startsWith('未能')) throw error
    if (error instanceof Error && (error.message.includes('超过') || error.message.includes('不支持'))) throw error
    console.error('[parseResumeFile] 解析失败:', error)
    throw new Error(`文件「${file.name}」解析失败，请重试或直接粘贴文本。`)
  }
}

/** 格式大类的展示名 */
export const KIND_LABEL: Record<ResumeFileKind, string> = {
  pdf: 'PDF',
  word: 'Word',
  image: '图片 OCR',
  text: '文本',
}
