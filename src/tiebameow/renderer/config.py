from typing import Literal

from pydantic import BaseModel


class Config(BaseModel):
    """
    渲染配置，width和height不应在此处设置，而应在渲染时传入。

    Attributes:
        quality (Literal["low", "medium", "high"]): 渲染质量，输出清晰度，默认为"medium"。
    """

    width: int = 500
    height: int = 100
    quality: Literal["low", "medium", "high"] = "medium"
