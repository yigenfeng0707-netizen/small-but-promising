# Dist - 项目产出物

此目录存放项目初赛提交的生成物。

## 文件清单

| 文件 | 说明 |
|------|------|
| `安居智评_PPT_v1.pptx` | 15 页演示 PPT（初赛提交） |
| `安居智评_项目文档_v1.pdf` | 项目文档 PDF（初赛提交） |

## 生成方式

- PPT：`python tools/archive/_generate_ppt.py`
- PDF：`pandoc docs/PROJECT_DOC.md -o dist/安居智评_项目文档_v1.pdf --pdf-engine=typst`
