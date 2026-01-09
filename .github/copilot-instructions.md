# TiebaMeow Copilot Instructions

## Project Overview
`tiebameow` is a modern Python 3.12+ library that standardizes interactions with Baidu Tieba. It wraps `aiotieba` for API access, uses SQLAlchemy for persistence, and Playwright for content rendering.

**Key Service Boundaries:**
1.  **Client Layer** (`src/tiebameow/client`): Handles all external API communication.
2.  **Parser Layer** (`src/tiebameow/parser`): Converts raw `aiotieba` responses -> Internal Pydantic DTOs.
3.  **Data Layer** (`src/tiebameow/models`):
    -   **DTO**: In-memory data exchange (Pydantic).
    -   **ORM**: Database persistence (SQLAlchemy).
    -   **Schemas**: Low-level content definitions (Fragments, Rules).
4.  **Renderer** (`src/tiebameow/renderer`): Visualizes DTOs using browser automation.

## Architecture & Patterns

### 1. Data Flow & Typing
- **Strict Separation**: NEVER pass raw `aiotieba` objects to the Renderer or ORM. Always convert them to DTOs first.
  - *Flow*: `Client` -> `aiotieba` response -> `Parser` -> `DTO` -> `Renderer` / `ORM`.
- **Fragments**: Content is not a simple string. It is a list of typed fragments (Text, Image, At, Link).
  - Use `src/tiebameow/schemas/fragments.py` for defining new content types.
  - In ORM, these are stored as JSON but typed via `FragmentListType`.

### 2. Client Implementation
- **Custom Wrapper**: Use `tiebameow.client.Client`, NOT `aiotieba.Client`.
  - It integrates `tenacity` for retries and `aiolimiter` for rate limiting.
- **Context Management**: Always use `async with Client() as client:` to ensure proper resource cleanup.

### 3. Database (ORM)
- **JSON Handling**: Use custom `TypeDecorator`s (`FragmentListType`, `RuleNodeType`) in `src/tiebameow/models/orm.py` when mapping Pydantic models to SQL JSON/JSONB columns.
- **Async Session**: The project uses asynchronous SQLAlchemy. Ensure all DB operations are awaited.

### 4. Rendering
- **Lifecycle**: `PlaywrightCore` manages the browser process. Do not instantiate Playwright manually in business logic.
- **Templates**: specific Jinja2 templates reside in `src/tiebameow/renderer/templates`.

## specific Conventions

### Language & Typing
- **Target**: Python 3.12+.
- **Import**: ALWAYS include `from __future__ import annotations` at the top of every file.
- **Hints**: Use modern syntax: `list[str]` over `List[str]`, `str | int` over `Union[str, int]`.
- **Runtime Check**: Use `if TYPE_CHECKING:` for circular import prevention.

### Error Handling
- **Specific Exceptions**: Catch `aiotieba.exception.TiebaServerError` for API failures.
- **Retrying**: Use `tenacity` decorators for network-bound operations.
- **Logging**: Use `src/tiebameow/utils/logger.py`.

## Developer Workflow

### Dependency Management (uv)
- **Tool**: Use `uv` for everything.
- **Install**: `uv sync` (installs dependencies from lockfile).
- **Add Pkg**: `uv add <package>` or `uv add --dev <package>`.
- **Run**: `uv run <command>`.

### Testing
- **Command**: `uv run pytest`.
- **Mocks**: `tests/conftest.py` contains dataclass mocks for `aiotieba` structs (e.g., `FragText`, `FragImage`) since `aiotieba` objects can be hard to instantiate directly. Use these for parser tests.
- **Async**: Use `@pytest.mark.asyncio` for async tests.

### Linting
- **Command**: `uv run pre-commit run --all-files`.
- **Policy**: Mypy strict mode is enabled. No `Any` unless absolutely necessary.

## Discovery Paths
- **New API Method**: Add to `src/tiebameow/client/tieba_client.py` -> Add Parser in `src/tiebameow/parser` -> Update DTO in `src/tiebameow/models/dto.py`.
- **New DB Table**: Define in `src/tiebameow/models/orm.py` -> Inherit from `Base`.
- **New Render Style**: Update `src/tiebameow/renderer/style.py` -> Edit Template in `src/tiebameow/renderer/templates`.
