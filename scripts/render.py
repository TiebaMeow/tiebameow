import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

from tiebameow.models.dto import (
    CommentDTO,
    CommentUserDTO,
    PostDTO,
    PostUserDTO,
    ThreadDTO,
    ThreadUserDTO,
)
from tiebameow.renderer import Renderer
from tiebameow.schemas.fragments import FragTextModel

OUTPUT_DIR = Path.cwd() / "dist" / "render_results"


class Manager:
    _renderer: Renderer | None = None

    @classmethod
    async def get_renderer(cls) -> Renderer:
        if cls._renderer is None:
            cls._renderer = Renderer()
            await cls._renderer.__aenter__()
        return cls._renderer

    @classmethod
    async def close(cls) -> None:
        if cls._renderer is not None:
            await cls._renderer.__aexit__(None, None, None)
            cls._renderer = None


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
                Path(output_path).write_bytes(image_bytes)  # noqa: ASYNC240

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


FAKE_THREAD_DTO = ThreadDTO.model_construct(
    tid=123456,
    pid=654321,
    fname="贴吧吧主",
    title="测试标题",
    author=ThreadUserDTO.model_construct(
        nick_name_new="测试作者",
        user_name="test_author",
        portrait="",
        level=6,
        user_id=1,
    ),
    contents=[FragTextModel(text="这是一个测试内容，用于渲染测试。")],
    create_time=1767196800,
    agree_num=10,
    share_num=5,
    reply_num=20,
)

FAKE_POST_DTO_LIST = [
    PostDTO.model_construct(
        tid=123456,
        pid=654322,
        floor=2,
        author=PostUserDTO.model_construct(
            nick_name_new="路人甲",
            user_name="lurenjia",
            portrait="",
            level=3,
            user_id=2,
        ),
        contents=[FragTextModel(text="前排围观")],
        create_time=1767196900,
        comments=[],
    ),
    PostDTO.model_construct(
        tid=123456,
        pid=654323,
        floor=3,
        author=PostUserDTO.model_construct(
            nick_name_new="路人乙",
            user_name="lurenyi",
            portrait="",
            level=4,
            user_id=3,
        ),
        contents=[FragTextModel(text="不明觉厉")],
        create_time=1767197000,
        comments=[
            CommentDTO.model_construct(
                author=CommentUserDTO.model_construct(
                    nick_name_new="路人甲",
                    user_name="lurenjia",
                    portrait="",
                    level=3,
                    user_id=2,
                ),
                contents=[FragTextModel(text="确实")],
                create_time=1767197100,
                tid=123456,
                pid=654323,
            )
        ],
    ),
    PostDTO.model_construct(
        tid=123456,
        pid=654324,
        floor=4,
        author=PostUserDTO.model_construct(
            nick_name_new="测试作者",
            user_name="test_author",
            portrait="",
            level=6,
            user_id=1,
        ),
        contents=[FragTextModel(text="自己顶一下")],
        create_time=1767197200,
        comments=[],
    ),
]


@register("thread_content.png")
async def render_thread_content() -> bytes:
    renderer = await Manager.get_renderer()
    return await renderer.render_content(FAKE_THREAD_DTO)


@register("thread_detail.png")
async def render_thread_detail() -> bytes:
    renderer = await Manager.get_renderer()
    return await renderer.render_thread_detail(
        thread=FAKE_THREAD_DTO,
        posts=FAKE_POST_DTO_LIST,
    )


@register("text_normal.png")
async def render_text_normal() -> bytes:
    renderer = await Manager.get_renderer()
    return await renderer.text_to_image(
        "这是一段普通的测试文本，用于测试文本渲染功能。\n这是第二行文本。\n    这是缩进文本。",
        title="普通文本渲染测试",
        header="tiebameow renderer",
        footer="第 1 页 / 共 5 页",
    )


@register("text_simple.png")
async def render_text_simple() -> bytes:
    renderer = await Manager.get_renderer()
    return await renderer.text_to_image(
        "这是一段极简样式的测试文本。\n这是第二行文本。\n    这是缩进的文本。",
        title="极简文本测试",
        header="页眉信息",
        footer="页脚信息",
        simple_mode=True,
    )


if __name__ == "__main__":
    import asyncio

    async def main() -> None:
        for fn in register_functions:
            await fn()
        await Manager.close()

    asyncio.run(main())
