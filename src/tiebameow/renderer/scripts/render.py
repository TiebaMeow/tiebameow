import os
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

from tiebameow.client import Client
from tiebameow.renderer import Renderer
from tiebameow.renderer.param import (
    CommentContent,
    PostContent,
    RenderContentParam,
    RenderThreadDetailParam,
    ThreadContent,
)

OUTPUT_DIR = Path.cwd() / "dist" / "render_results"


class Manager:
    _renderer: Renderer | None = None
    _client: Client | None = None

    @classmethod
    async def get_renderer(cls) -> Renderer:
        if cls._renderer is None:
            cls._renderer = Renderer()
            await cls._renderer.__aenter__()
        return cls._renderer

    @classmethod
    async def get_client(cls) -> Client:
        if cls._client is None:
            cls._client = Client()
            await cls._client.__aenter__()
        return cls._client

    @classmethod
    async def close(cls) -> None:
        if cls._renderer is not None:
            await cls._renderer.__aexit__(None, None, None)
            cls._renderer = None
        if cls._client is not None:
            await cls._client.__aexit__(None, None, None)
            cls._client = None


register_functions: list[Callable[[], Awaitable[None]]] = []


def register(filename: str) -> Callable[[Callable[[], Awaitable[bytes]]], Callable[[], Awaitable[bytes]]]:
    def wrapper(fn: Callable[[], Awaitable[bytes]]) -> Callable[[], Awaitable[bytes]]:
        async def _() -> None:
            is_gh_actions = os.getenv("GITHUB_ACTIONS") == "true"
            task_name = f"Render {filename}"

            if is_gh_actions:
                print(f"::group::{task_name}")
            else:
                print(f"--- Starting: {task_name} ---")

            start_time = time.time()
            try:
                image_bytes = await fn()
                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                output_path = OUTPUT_DIR / filename
                with Path(output_path).open("wb") as f:  # noqa: ASYNC230
                    f.write(image_bytes)

                elapsed = time.time() - start_time
                size_kb = len(image_bytes) / 1024
                print(f"Successfully rendered to {output_path}")
                print(f"Size: {size_kb:.2f} KB")
                print(f"Time elapsed: {elapsed:.2f}s")

            except Exception as e:
                if is_gh_actions:
                    print(f"::error file={__file__},title=Render Failed::{str(e)}")
                print(f"Error rendering {filename}: {e}", file=sys.stderr)
                raise e
            finally:
                if is_gh_actions:
                    print("::endgroup::")
                else:
                    print(f"--- Finished: {task_name} ---\n")

        register_functions.append(_)
        return fn

    return wrapper


FAKE_THREAD_CONTENT = ThreadContent(
    tid=123456,
    pid=654321,
    title="测试标题",
    nick_name="测试作者",
    text="这是一个测试内容，用于渲染测试。",
    create_time=1767196800,
    level=6,
    portrait="",
    image_hash_list=[],
)

FAKE_POST_CONTENT_LIST = [
    PostContent(
        tid=123456,
        pid=654322,
        floor=2,
        nick_name="路人甲",
        text="前排围观",
        create_time=1767196900,
        level=3,
        portrait="",
        image_hash_list=[],
        comments=[],
    ),
    PostContent(
        tid=123456,
        pid=654323,
        floor=3,
        nick_name="路人乙",
        text="不明觉厉",
        create_time=1767197000,
        level=4,
        portrait="",
        image_hash_list=[],
        comments=[
            CommentContent(
                nick_name="路人甲",
                text="确实",
                create_time=1767197100,
                tid=123456,
                pid=654323,
            )
        ],
    ),
    PostContent(
        tid=123456,
        pid=654324,
        floor=4,
        nick_name="测试作者",
        text="自己顶一下",
        create_time=1767197200,
        level=6,
        portrait="",
        image_hash_list=[],
        comments=[],
    ),
]


@register("thread_content.png")
async def render_thread_content() -> bytes:
    renderer = await Manager.get_renderer()
    return await renderer.render_content(
        RenderContentParam(
            content=FAKE_THREAD_CONTENT,
            forum="贴吧吧主",
        )
    )


@register("thread_detail.png")
async def render_thread_detail() -> bytes:
    renderer = await Manager.get_renderer()
    return await renderer.render_thread_detail(
        RenderThreadDetailParam(
            thread=FAKE_THREAD_CONTENT,
            posts=FAKE_POST_CONTENT_LIST,
            forum="贴吧吧主",
        )
    )


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        for fn in register_functions:
            await fn()
        await Manager.close()

    asyncio.run(main())
