# tiebameow

[![License](https://img.shields.io/github/license/TiebaMeow/tiebameow)](https://github.com/TiebaMeow/tiebameow/blob/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/tiebameow)](https://pypi.org/project/tiebameow/)
[![Python](https://img.shields.io/pypi/pyversions/tiebameow)](https://pypi.org/project/tiebameow/)
[![CI](https://github.com/TiebaMeow/tiebameow/actions/workflows/CI.yml/badge.svg)](https://github.com/TiebaMeow/tiebameow/actions/workflows/CI.yml)
[![codecov](https://codecov.io/gh/TiebaMeow/tiebameow/graph/badge.svg)](https://codecov.io/gh/TiebaMeow/tiebameow)

Tiebameow 项目通用模块

## 简介

`tiebameow` 是在 Tiebameow 项目内使用的通用模块，提供了通用的数据模型、序列化/反序列化工具、日志模块以及辅助函数。

## 目录

- `client`: 包含增强的 `aiotieba.Client` 与 `httpx` 客户端。
- `models`: 定义了通用数据交换模型和 ORM 数据模型。
- `parser`: 提供解析和处理 `aiotieba` 数据和审查规则的解析器。
- `renderer`: 提供将 DTO 内容或简单文本渲染为图片的功能。
- `schemas`: 定义了各种数据片段与审查规则的 Pydantic 模型。
- `serializer`: 提供数据交换模型的序列化和反序列化方法。
- `utils`: 包含通用日志模块和一些辅助函数和工具类。

## 安装

推荐使用 `uv` 进行环境管理和依赖安装。

仅安装基础功能：

```bash
uv add tiebameow
```

如需使用数据库模型，请安装 `orm` 额外依赖：

```bash
uv add tiebameow[orm]
```

如需使用渲染功能，请安装 `renderer` 额外依赖和 `Playwright` 所需浏览器：

```bash
uv add tiebameow[renderer]
uv run playwright install chromium-headless-shell
```

## 基本用法

更多用法请参阅源码。

### Client

#### Tieba Client

```python
from tiebameow.client import Client
async with Client() as client:
    user_info = await client.get_user_info("some_username")
```

#### HTTP Client

```python
from tiebameow.client import HTTPXClient
response = await HTTPXClient.get("https://example.com")
```

### Parser

#### 数据转换器

将 `aiotieba` 对象转换为通用数据交换模型：

```python
from tiebameow.parser import convert_aiotieba_thread
from tiebameow.client import Client
async with Client() as client:
    threads = await client.get_threads("some_tieba")
    for thread in threads:
        converted_thread = convert_aiotieba_thread(thread)
```

#### 规则引擎解析器

以 DSL 或 CNL 模式解析规则和动作：

```python
from tiebameow.parser import RuleEngineParser
parser = RuleEngineParser()
rule_node = parser.parse_rule("(title contains 'A' AND title contains 'B') OR NOT title contains 'C'")
actions = parser.parse_actions("DO: delete(reason='spam content'), ban(days=1)")
```

### Renderer

```python
from tiebameow.renderer import Renderer
async with Renderer() as renderer:
    image_bytes = await renderer.text_to_image("Hello, World!")
```

## 开发指南

欢迎贡献代码，请确保遵循项目的编码规范，并在提交前运行 pre-commit hooks:

```bash
uv sync --dev
pre-commit install
pre-commit run --all-files
```

有关详细信息，请参阅 `CONTRIBUTING.md` 文件。
