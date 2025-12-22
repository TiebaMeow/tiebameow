# tiebameow

Tiebameow 项目通用模块

## 简介

`tiebameow` 是在 Tiebameow 项目内使用的通用模块，提供了通用的数据模型、序列化/反序列化工具、日志模块以及辅助函数。

## 目录

- `client`: 包含增强的 `aiotieba.Client` 与 `httpx` 客户端。
- `models`: 定义了通用数据交换模型和 ORM 数据模型。
- `parser`: 提供解析和处理 `aiotieba` 数据的解析器。
- `schemas`: 定义了各种数据片段的 Pydantic 模型。
- `serializer`: 提供数据交换模型的序列化和反序列化方法。
- `utils`: 包含通用日志模块和一些辅助函数和工具类。

## 开发指南

欢迎贡献代码，请确保遵循项目的编码规范，并在提交前运行 pre-commit hooks:

```bash
uv sync --dev
pre-commit install
pre-commit run --all-files
```

有关详细信息，请参阅 `CONTRIBUTING.md` 文件。
