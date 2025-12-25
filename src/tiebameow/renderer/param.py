from datetime import datetime

from pydantic import BaseModel, field_validator


class ThreadRenderParam(BaseModel):
    """
    帖子渲染参数

    Args:
        title: 帖子标题
        text: 帖子内容文本
        create_time: 帖子创建时间
        nick_name: 作者昵称
        level: 作者等级
        portrait: 头像标识符
        portrait_base64: 头像的 Base64 编码字符串
        image_hash_list: 帖子中包含的图片哈希列表
        image_base64_list: 帖子中包含的图片的 Base64 编码字符串列表
        remain_image_count: 未包含在 image_base64_list 中的图片数量
        prefix_html: 渲染结果前缀 HTML 代码
        suffix_html: 渲染结果后缀 HTML 代码
    """

    title: str

    text: str

    create_time: datetime | int | float
    """帖子创建时间。支持 datetime 对象，或自 Unix 纪元以来的秒/毫秒时间戳（int/float）。
    若为时间戳，推荐传入秒（10位），如为毫秒（13位），会自动转换。"""

    nick_name: str

    level: int = 0

    portrait: str = ""

    portrait_url: str = ""
    """头像的 url。如果提供此字段，则优先使用此字段渲染头像。否则使用 portrait 字段获取头像。"""

    image_hash_list: list[str] = []

    image_url_list: list[str] = []
    """帖子中包含的图片的 url 列表。如果提供此字段，
    则优先使用此字段渲染图片。否则使用 image_hash_list 字段获取图片。"""

    remain_image_count: int = 0
    """未包含在 image_url_list 中的图片数量。自动计算填写，无需手动设置。"""

    prefix_html: str = ""

    suffix_html: str = ""

    @field_validator("create_time", mode="before")
    @classmethod
    def convert_timestamp(cls, v: int | float | datetime) -> datetime:
        if isinstance(v, (int, float)):
            # 判断是否为毫秒级时间戳（大于 10^11，约为 5138 年）
            if v > 1e11:
                v = v / 1000
            return datetime.fromtimestamp(v)
        return v
