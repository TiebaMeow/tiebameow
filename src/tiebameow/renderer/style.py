from functools import lru_cache
from pathlib import Path

__all__ = ["get_font_style", "font_path", "FONT_URL"]

font_path = Path(__file__).parent / "static" / "fonts" / "NotoSansSC-Regular.woff2"
FONT_URL = "http://tiebameow.local/fonts/NotoSansSC-Regular.woff2"


@lru_cache(maxsize=1)
def get_font_style(font_size: int = 14) -> str:
    if not font_path.exists():
        return f"""<style>
body {{
    font-family: "Noto Sans SC", "Noto Sans CJK SC", sans-serif;
    font-size: {font_size}px;
}}
</style>
"""

    # 使用虚拟URL代替Base64嵌入，由Playwright拦截请求并加载本地文件
    return f"""<style>
@font-face {{
    font-family: 'Noto Sans SC';
    font-style: normal;
    font-weight: 400;
    src: url("{FONT_URL}") format('woff2');
}}

body {{
    font-family: "Noto Sans SC", "Noto Sans CJK SC", sans-serif;
    font-size: {font_size}px;
}}
</style>
"""
