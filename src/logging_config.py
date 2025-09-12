"""日志配置模块

提供统一的日志配置和管理功能，支持控制台、文件和性能日志。
使用 loguru 作为底层日志库，提供结构化日志和性能监控功能。

主要功能：
- 多种日志输出格式（控制台、文件、性能）
- 日志轮转和压缩
- 结构化日志记录
- 性能监控日志
- 日志统计信息
"""

import sys
from pathlib import Path
from typing import Dict, Any
from loguru import logger


class LoggingConfig:
    """日志配置类

    提供统一的日志配置管理，支持多种输出方式和格式。
    使用 loguru 作为底层日志库，提供高性能和灵活的日志功能。
    """

    # 文件日志格式
    FILE_FORMAT = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
        "{name}:{function}:{line} | {message}"
    )

    # 控制台日志格式（带颜色）
    CONSOLE_FORMAT = (
        "<green>{time:HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:"
        "<cyan>{line}</cyan> | {message}"
    )

    # 性能日志格式
    PERFORMANCE_FORMAT = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | PERF | "
        "{extra[operation]} | {extra[duration]:.3f}s | {message}"
    )

    def __init__(self, log_level: str = "INFO", logs_dir: str = "logs") -> None:
        """初始化日志配置

        Args:
            log_level: 日志级别，默认为 INFO
            logs_dir: 日志文件目录，默认为 logs
        """
        self.log_level = log_level.upper()
        self.logs_dir = Path(logs_dir)
        self.logs_dir.mkdir(exist_ok=True)

        # 日志文件路径
        self.app_log_file = self.logs_dir / "app.log"
        self.error_log_file = self.logs_dir / "error.log"
        self.performance_log_file = self.logs_dir / "performance.log"

        # 清除默认处理器
        logger.remove()

    def setup_logging(self,
                      enable_console: bool = True,
                      enable_file: bool = True,
                      enable_performance: bool = False) -> None:
        """设置日志配置

        Args:
            enable_console: 是否启用控制台日志
            enable_file: 是否启用文件日志
            enable_performance: 是否启用性能日志
        """
        try:
            if enable_console:
                self._setup_console_logging()

            if enable_file:
                self._setup_file_logging()

            if enable_performance:
                self._setup_performance_logging()

            logger.info(f"日志系统初始化完成，级别: {self.log_level}")

        except Exception as e:
            # 如果配置失败，至少保证基本的控制台输出
            logger.add(sys.stderr, level="ERROR")
            logger.error(f"日志配置失败: {e}")
            raise

    def _setup_file_logging(self) -> None:
        """设置文件日志"""
        # 应用日志（所有级别）
        logger.add(
            self.app_log_file,
            format=self.FILE_FORMAT,
            level=self.log_level,
            rotation="10 MB",
            retention="30 days",
            compression="zip",
            encoding="utf-8",
            enqueue=True  # 异步写入
        )

        # 错误日志（仅错误和严重错误）
        logger.add(
            self.error_log_file,
            format=self.FILE_FORMAT,
            level="ERROR",
            rotation="5 MB",
            retention="60 days",
            compression="zip",
            encoding="utf-8",
            enqueue=True
        )

    def _setup_console_logging(self) -> None:
        """设置控制台日志"""
        logger.add(
            sys.stderr,
            format=self.CONSOLE_FORMAT,
            level=self.log_level,
            colorize=True
        )

    def _setup_performance_logging(self) -> None:
        """设置性能日志"""
        logger.add(
            self.performance_log_file,
            format=self.PERFORMANCE_FORMAT,
            level="INFO",
            filter=lambda record: "performance" in record["extra"],
            rotation="5 MB",
            retention="7 days",
            encoding="utf-8"
        )

    @staticmethod
    def log_performance(operation: str, duration: float,
                        details: str = "") -> None:
        """记录性能日志

        Args:
            operation: 操作名称
            duration: 执行时间（秒）
            details: 详细信息
        """
        logger.bind(performance=True, operation=operation,
                    duration=duration).info(
            f"操作完成: {details}" if details else "操作完成"
        )

    @staticmethod
    def log_structured(level: str, event: str, **kwargs: Any) -> None:
        """记录结构化日志

        Args:
            level: 日志级别
            event: 事件描述
            **kwargs: 结构化数据
        """
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(event)

    def get_log_stats(self) -> Dict[str, Any]:
        """获取日志统计信息

        Returns:
            包含日志文件信息的字典
        """
        stats: Dict[str, Any] = {
            "log_directory": str(self.logs_dir),
            "log_level": self.log_level,
            "log_files": []
        }

        log_files_list = stats["log_files"]

        for log_file in [self.app_log_file, self.error_log_file,
                         self.performance_log_file]:
            if log_file.exists():
                log_files_list.append({
                    "name": log_file.name,
                    "path": str(log_file),
                    "size": log_file.stat().st_size,
                    "modified": log_file.stat().st_mtime
                })

        return stats


def setup_default_logging(
        log_level: str = "INFO",
        logs_dir: str = "logs") -> LoggingConfig:
    """设置默认日志配置

    Args:
        log_level: 日志级别
        logs_dir: 日志目录

    Returns:
        配置好的 LoggingConfig 实例
    """
    logging_config = LoggingConfig(log_level, logs_dir)
    logging_config.setup_logging()
    return logging_config
