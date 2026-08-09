# pdf-to-study-notes

把课件 PDF（数字版或扫描件、中文或英文）转成**带层级、可直接背的 Markdown 学习笔记**。

anydoc 给你"能读的 Markdown"，我们给你"能背的笔记"：扫描件 OCR 内置、标题层级来自真实字号/字高、水印自动过滤，最后还有一步 LLM 语义清洗（纠错、层级重排、补缺标注、逻辑衔接）。

## 特性

- **扫描件中文 PDF 端到端**：内置 OCR + 水印过滤 + 字高推断层级，无需外挂 OCR 服务；
- **两段式流水线**：机械转换（快、稳、省 token）→ LLM 语义清洗（可选的第二个脚本由 AI 按规则执行）；
- **轻量**：核心依赖只有 PyMuPDF（约 54 MB）；OCR 惰性加载，纯数字版永远不碰 OCR 全家桶（约 148 MB 全装）；
- **可溯源**：保留 `<!-- 第 N 页 -->` 页标记、原始转换版备份，补注内容统一标 `【补充】`；
- **离线可用**：不上传文件、不调云 API。

## 安装

```bash
# 轻量版（只处理带文字层的 PDF）
pip install pymupdf

# 完整版（支持扫描件 OCR）
pip install pymupdf rapidocr_onnxruntime pillow
```

## 快速开始

```bash
# 转换（自动识别文字层 / 扫描页）
python scripts/convert.py <课件.pdf 或目录> -o out/

# 机械预清洗（去水印、压空行、降级碎片标题）
python scripts/mech_clean.py out/xxx.md mech/xxx.md

# 第三步：按 references/cleanup-guide.md 的规则做 LLM 语义清洗
```

参数：`--dpi`（默认 170，扫描件速度与质量的平衡点）、`--min-chars`、`--watermark-ratio`。

## 输出约定

- `#` 文件标题 / `##` 章节 / `###` 小节 / `####` 知识点；
- 每页保留 `<!-- 第 N 页 -->` 标记，可对照原 PDF；
- 整理时补充/校正的内容统一标 `【补充：…】`；
- 格式示例见 [assets/example.md](assets/example.md)，清洗规则见 [references/cleanup-guide.md](references/cleanup-guide.md)。

## 与同类工具对比

| 维度 | anydoc | MinerU | 本 skill |
| --- | --- | --- | --- |
| 扫描件中文 PDF | 不支持（需外部 OCR） | 支持 | 支持 |
| 标题层级 | 文字层 PDF 层级弱 | 本地默认全部 `#`（需 LLM 辅助） | 字号/字高真实分层 |
| 二次清洗成笔记 | 无 | 无 | 有（LLM 语义清洗） |
| 安装体积 | npx + Rust 工具链 | 模型数 GB | ~54 MB（纯数字版） |
| 离线 | 是 | 是 | 是 |

## 依赖与许可证

| 依赖 | 许可证 | 用途 |
| --- | --- | --- |
| PyMuPDF | AGPL-3.0 | 文字层提取 + 页面渲染 |
| rapidocr_onnxruntime | Apache-2.0 | 扫描件 OCR |
| Pillow | HPND | 图片处理 |

> 许可证待定：若本仓库整体采用 AGPL-3.0，可与 PyMuPDF 直接兼容；如需宽松许可（如 MIT），需将 PyMuPDF 列为可选依赖并在运行时安装。

## 参考与致谢

- 目录结构与打包规范遵循 OpenAI [skill-creator](https://github.com/openai/codex) 约定；
- 对比评估过 [firecrawl/anydoc](https://github.com/firecrawl/anydoc)、[MinerU](https://github.com/opendatalab/MinerU)、md-reheader 等方案，最终选择"PyMuPDF + RapidOCR + LLM 清洗"的轻量路线（评估过程见上表）。
