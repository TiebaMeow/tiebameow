from datetime import datetime
from zoneinfo import ZoneInfo

SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def now_with_tz() -> datetime:
    """返回带时区的当前时间。

    Returns:
        datetime: 上海时区的当前时间。
    """
    return datetime.now(SHANGHAI_TZ)
