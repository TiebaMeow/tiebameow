from typing import Literal

from pydantic import BaseModel


class RenderConfig(BaseModel):
    """
    Attributes:
        width (int): 渲染宽度，默认为500。
        height (int): 渲染高度，无需手动调整高度，默认为100。
        quality (Literal["low", "medium", "high"]): 渲染质量，输出清晰度，默认为"medium"。
    """

    width: int = 500
    height: int = 100
    quality: Literal["low", "medium", "high"] = "medium"
