# samples/ 演示样本

本目录存放**可直接复现演示**的简历与岗位样本，供答辩演示、端到端联调与冒烟测试使用。

## 文件清单

| 文件 | 来源 | 规模 | 用途 |
|---|---|---|---|
| `resume_short.txt` | `脱敏资料/resume_20.pdf` | 1 页 / 1834 字符 | 短简历，用于触发 `INSUFFICIENT_DETAIL` / `TOO_SHORT` 质量问题 |
| `resume_mid.txt` | `脱敏资料/resume_05.pdf` | 2 页 / 3361 字符 | 中等规模，常规匹配演示 |
| `resume_long.txt` | `脱敏资料/resume_18.pdf` | 6 页 / 8494 字符 | 长简历，用于长文本截断与耗时演示 |
| `jd_java.txt` | 手写（参照主流招聘网站 Java 岗位） | — | Java 后端岗 JD，含必备/加分项区分 |
| `jd_frontend.txt` | 手写（参照主流招聘网站前端岗位） | — | 前端 Vue 岗 JD，含必备/加分项区分 |

## 复现方式

样本由 `scripts/extract-pdf.py` 从脱敏 PDF 抽取（PDF 已确认含完整文本层，无需 OCR）：

```bash
# 列出全部脱敏 PDF 的页数与字符数
python scripts/extract-pdf.py --list

# 重新生成三份简历样本
python scripts/extract-pdf.py --src "../脱敏资料" --out "samples"
```

## 隐私说明

- 原始 PDF 位于仓库外的 `脱敏资料/` 目录，**不纳入版本控制**。
- 抽取文本保留的均为工作经历 / 技能等技术信息；姓名、电话、邮箱、身份证号在 PDF 脱敏阶段已移除。
- 文本中残留的形如 `57ffaa90...` 的长串为 PDF 水印/校验标识，非敏感个人信息。

## 答辩演示组合（对应 Checklist 7.1）

1. `resume_short.txt` + `jd_java.txt` —— 演示短简历质量问题 + Java 岗匹配
2. `resume_long.txt` + `jd_frontend.txt` —— 演示长简历耗时 + 前端岗匹配
