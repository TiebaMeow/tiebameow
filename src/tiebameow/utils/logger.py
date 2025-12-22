import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from types import FrameType

__all__ = ["logger", "init_logger"]


class InterceptHandler(logging.Handler):
    """
    拦截标准日志消息并将其路由到 Loguru。
    """

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame: FrameType | None = logging.currentframe()
        depth = 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def init_logger(
    *,
    service_name: str = "tiebameow",
    level: str = "INFO",
    console_format: str | None = None,
    enable_filelog: bool = False,
    enable_error_filelog: bool = False,
    log_dir: str | Path = "logs",
    file_format: str | None = None,
    rotation: str = "00:00",
    retention: str = "14 days",
    intercept_standard_logging: bool = True,
    enqueue: bool = True,
    diagnose: bool = True,
    reset: bool = True,
    add_console: bool = True,
) -> None:
    """
    使用标准配置初始化适用于 TiebaMeow 服务的 loguru logger。

    Args:
        service_name: 服务名称，用于日志文件命名。

        level: 最低日志级别（例如 "DEBUG", "INFO"）。
        console_format: 控制台输出的自定义格式。
        enable_filelog: 是否启用日志文件记录。
        enable_error_filelog: 是否启用错误日志文件记录。
        log_dir: 日志文件存储目录。
        file_format: 文件输出的自定义格式。
        rotation: 日志轮转条件（例如 "1 day", "500 MB", "00:00"）。
        retention: 日志保留条件（例如 "10 days"）。
        intercept_standard_logging: 是否拦截标准库日志。
        enqueue: 是否使用线程安全的日志记录（异步安全）。
        diagnose: 是否在异常回溯中显示变量值。
        reset: 是否移除所有现有的处理器。如果集成到已有日志记录的应用中（例如 NoneBot），请设置为 False。
        add_console: 是否添加控制台处理器。如果应用已经有一个，请设置为 False。
    """
    if console_format is None:
        console_format = (
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> "
            "<level>[{level}]</level> "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        )

    if reset:
        logger.remove()

    if add_console:
        logger.add(
            sys.stderr,
            format=console_format,
            level=level,
            enqueue=enqueue,
            diagnose=diagnose,
        )

    if enable_filelog or enable_error_filelog:
        if file_format is None:
            file_format = "{time:YYYY-MM-DD HH:mm:ss} [{level}] {name}:{function}:{line} | {message}"

        log_path = Path(log_dir)
        try:
            log_path.mkdir(parents=True, exist_ok=True)
        except Exception:
            logger.warning("Failed to create log directory: {}, file logging disabled.", log_path)
            return

        if enable_filelog:
            logger.add(
                log_path / f"{service_name}.log",
                format=file_format,
                level=level,
                rotation=rotation,
                retention=retention,
                encoding="utf-8",
                enqueue=enqueue,
                compression="zip",
                diagnose=diagnose,
            )

        if enable_error_filelog:
            logger.add(
                log_path / f"{service_name}.error.log",
                format=file_format,
                level="ERROR",
                rotation=rotation,
                retention=retention,
                encoding="utf-8",
                enqueue=enqueue,
                compression="zip",
                diagnose=diagnose,
            )

    if intercept_standard_logging:
        logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
