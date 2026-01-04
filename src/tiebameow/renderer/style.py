import base64
from functools import lru_cache
from pathlib import Path

font_path = Path(__file__).parent / "static" / "fonts" / "NotoSansSC-Regular.woff2"


@lru_cache(maxsize=1)
def get_font_style() -> str:
    if not font_path.exists():
        return """<style>
body {
    font-family: "Noto Sans SC", "Noto Sans CJK SC", sans-serif;
    font-size: 14px;
}
</style>
"""

    with font_path.open("rb") as f:
        font_data = base64.b64encode(f.read()).decode("utf-8")
    return f"""<style>
@font-face {{
    font-family: 'Noto Sans SC';
    font-style: normal;
    font-weight: 400;
    src: url(data:font/woff2;base64,{font_data}) format('woff2');
}}

body {{
    font-family: "Noto Sans SC", "Noto Sans CJK SC", sans-serif;
    font-size: 14px;
}}
</style>
"""
