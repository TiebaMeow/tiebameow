from pathlib import Path

font_path = Path(__file__).parent / "static" / "fonts" / "NotoSansSC-Regular.woff2"
FONT_STYLE = f"""<style>
@font-face {{
    font-family: 'Noto Sans SC';
    font-style: normal;
    font-weight: 400;
    src: url('{font_path.as_uri()}') format('woff2');
}}

body {{
    font-family: "Noto Sans SC", "Noto Sans CJK SC", sans-serif;
    font-size: 14px;
}}
</style>
"""