# 📄 pdf-to-study-notes

把课件 PDF（数字版或扫描件、中英文都行）变成**带层级、能直接背的 Markdown 学习笔记**。

![banner](https://socialify.git.ci/zoey1yang/pdf-to-study-notes/image?description=1&font=Raleway&language=1&name=1&owner=1&pattern=Circuit%20Board&theme=Light)

## 它能做什么

- 🔍 **扫描件也能读**：内置 OCR，中英文扫描件直接转文字，不用外挂服务
- 🧱 **还原真实层级**：按字号 / 字高推断标题级别，还原 `#` 到 `####`
- 🧹 **水印自动过滤**：机械清洗去水印、压空行、修碎片标题
- 🧠 **AI 语义清洗**：可选一步 LLM 清洗，纠错、补缺、逻辑衔接，可直接背
- 💾 **离线轻量**：核心依赖只有 PyMuPDF（约 54MB），不上传文件

## 快速开始

```bash
# 轻量版（数字版 PDF）
pip install pymupdf

# 完整版（扫描件 OCR）
pip install pymupdf rapidocr_onnxruntime pillow

# 转换
python scripts/convert.py 课件.pdf -o out/
```

转换 → 清洗 → 开背，就这么简单。详细用法见 [SKILL.md](SKILL.md)。

转换完记得跑一次题号自检，把疑似漏题/并题列出来对照原 PDF 核对：

```bash
python scripts/audit_questions.py out/课件.md -o 可疑清单.md
```

## 和同类工具比

| 维度 | anydoc | MinerU | 本工具 |
| --- | --- | --- | --- |
| 扫描件中文 PDF | ✗ | ✓ | ✓ |
| 还原标题层级 | 弱 | 全变 `#` | 字号真实分层 |
| 二次清洗成笔记 | ✗ | ✗ | ✓（AI 清洗） |
| 安装体积 | npx + 工具链 | 数 GB | ~54MB |
| 离线 | ✓ | ✓ | ✓ |

## 更多

- 输出示例：[assets/example.md](assets/example.md)
- 清洗规则：[references/cleanup-guide.md](references/cleanup-guide.md)
- 小红书海报素材：[assets/posters/](assets/posters/)
- 许可证：AGPL-3.0（[LICENSE](LICENSE)，与 PyMuPDF 兼容）

喜欢的话点个 ⭐ 支持一下～
