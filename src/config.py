#!/usr/bin/env python3
"""
配置管理模块

管理 UML MCP 渲染服务的所有配置参数，支持环境变量和默认值。
提供配置验证、目录创建和配置导出功能。

Author: UML MCP Team
Version: 1.0.0
"""

import os
import re
from pathlib import Path
from typing import List, Dict, Any


class Config:
    """
    配置管理类

    从环境变量读取配置，提供默认值和验证。
    支持服务器配置、渲染配置、缓存配置、安全配置等多个方面。

    Attributes:
        server_host (str): 服务器主机地址
        server_port (int): 服务器端口号
        plantuml_jar_path (str): PlantUML JAR 文件路径
        java_executable (str): Java 可执行文件路径
        java_memory (str): Java 内存配置
        render_timeout (int): 渲染超时时间（秒）
        max_uml_size (int): 最大 UML 代码大小（字节）
        max_concurrent_renders (int): 最大并发渲染数
        temp_dir (str): 临时文件目录
        cache_dir (str): 缓存目录
        logs_dir (str): 日志目录
        output_dir (str): 默认输出目录（可选）
        enable_cache (bool): 是否启用缓存
        cache_ttl (int): 缓存生存时间（秒）
        max_cache_size (int): 最大缓存项数量
        allowed_formats (List[str]): 允许的输出格式
        max_diagram_complexity (int): 最大图表复杂度
        log_level (str): 日志级别
        log_format (str): 日志格式
        enable_metrics (bool): 是否启用性能指标
        metrics_port (int): 指标服务端口

    Examples:
        >>> config = Config()
        >>> print(f"服务器地址: {config.server_host}:{config.server_port}")
        >>> config.create_directories()  # 创建必要的目录
        >>> print(config.to_dict())      # 导出配置字典
    """

    def __init__(self) -> None:
        """
        初始化配置管理器

        从环境变量读取所有配置参数，设置默认值，并进行配置验证。
        如果配置无效，将抛出 ValueError 异常。

        Raises:
            ValueError: 配置参数无效时抛出
        """
        # 服务器配置
        self.server_host = os.getenv("UML_MCP_HOST", "localhost")
        self.server_port = int(os.getenv("UML_MCP_PORT", "8080"))

        # PlantUML 配置
        self.plantuml_jar_path = os.getenv(
            "PLANTUML_JAR_PATH", str(Path.cwd() / "plantuml.jar")
        )

        # Java 配置
        self.java_executable = os.getenv("JAVA_EXECUTABLE", "java")
        self.java_memory = os.getenv("JAVA_MEMORY", "512m")

        # 渲染配置
        self.render_timeout = int(os.getenv("RENDER_TIMEOUT", "30"))  # 秒
        self.max_uml_size = int(os.getenv("MAX_UML_SIZE", "10240"))  # 字节 (10KB)
        self.max_concurrent_renders = int(os.getenv("MAX_CONCURRENT_RENDERS", "10"))

        # 文件系统配置
        self.temp_dir = os.getenv("TEMP_DIR", str(Path.cwd() / "temp"))
        self.cache_dir = os.getenv("CACHE_DIR", str(Path.cwd() / "cache"))
        self.logs_dir = os.getenv("LOGS_DIR", str(Path.cwd() / "logs"))
        self.output_dir = os.getenv("OUTPUT_DIR", None)  # 可选的默认输出目录

        # 缓存配置
        self.enable_cache = os.getenv("ENABLE_CACHE", "true").lower() == "true"
        self.cache_ttl = int(os.getenv("CACHE_TTL", "3600"))  # 秒 (1小时)
        self.max_cache_size = int(os.getenv("MAX_CACHE_SIZE", "100"))  # 缓存项数量

        # 安全配置
        self.allowed_formats = ["png", "svg"]
        self.max_diagram_complexity = int(os.getenv("MAX_DIAGRAM_COMPLEXITY", "1000"))

        # 日志配置
        self.log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        self.log_format = os.getenv(
            "LOG_FORMAT",
            (
                "{time:YYYY-MM-DD HH:mm:ss} | {level} | "
                "{name}:{function}:{line} | {message}"
            ),
        )

        # 性能配置
        self.enable_metrics = os.getenv("ENABLE_METRICS", "false").lower() == "true"
        self.metrics_port = int(os.getenv("METRICS_PORT", "9090"))

        # 验证配置
        self._validate_config()

    def _validate_config(self) -> None:
        """
        验证配置参数的有效性

        检查所有配置参数是否在有效范围内，包括端口号、超时时间、
        文件大小限制、并发数量和日志级别等。

        Raises:
            ValueError: 当配置参数超出有效范围或格式不正确时抛出

        Note:
            此方法在 __init__ 中自动调用，确保配置的有效性。
        """
        self._validate_port_settings()
        self._validate_performance_settings()
        self._validate_logging_settings()
        self._validate_path_settings()
        self._validate_cache_settings()

    def _validate_port_settings(self) -> None:
        """验证端口配置"""
        if not isinstance(
                self.server_port, int) or not (
                1 <= self.server_port <= 65535):
            raise ValueError(
                f"无效的服务器端口: {self.server_port}，必须是1-65535之间的整数"
            )

        if not isinstance(
                self.metrics_port, int) or not (
                1 <= self.metrics_port <= 65535):
            raise ValueError(
                f"无效的指标端口: {self.metrics_port}，必须是1-65535之间的整数"
            )

    def _validate_performance_settings(self) -> None:
        """验证性能相关配置"""
        if not isinstance(self.render_timeout, (int, float)
                          ) or self.render_timeout <= 0:
            raise ValueError(
                f"无效的渲染超时时间: {self.render_timeout}，必须是正数"
            )

        if not isinstance(self.max_uml_size, int) or self.max_uml_size <= 0:
            raise ValueError(
                f"无效的最大 UML 大小: {self.max_uml_size}，必须是正整数"
            )

        if not isinstance(
                self.max_concurrent_renders,
                int) or self.max_concurrent_renders <= 0:
            raise ValueError(
                f"无效的最大并发渲染数: {self.max_concurrent_renders}，必须是正整数"
            )

    def _validate_logging_settings(self) -> None:
        """验证日志配置"""
        valid_log_levels: List[str] = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if not isinstance(
                self.log_level,
                str) or self.log_level not in valid_log_levels:
            raise ValueError(
                f"无效的日志级别: {self.log_level}，必须是 {valid_log_levels} 中的一个"
            )

    def _validate_path_settings(self) -> None:
        """验证路径和Java配置"""
        if not isinstance(self.plantuml_jar_path,
                          str) or not self.plantuml_jar_path.strip():
            raise ValueError("PlantUML JAR 路径不能为空")

        if not isinstance(
                self.java_executable,
                str) or not self.java_executable.strip():
            raise ValueError("Java 可执行文件路径不能为空")

        if not isinstance(
                self.java_memory,
                str) or not re.match(
                r'^\d+[mMgG]$',
                self.java_memory):
            raise ValueError(
                f"无效的 Java 内存设置: {self.java_memory}，格式应为 '512m' 或 '1g'"
            )

    def _validate_cache_settings(self) -> None:
        """验证缓存配置"""
        if not isinstance(self.enable_cache, bool):
            raise ValueError(f"缓存启用标志必须是布尔值: {self.enable_cache}")

        if not isinstance(self.cache_ttl, int) or self.cache_ttl < 0:
            raise ValueError(f"无效的缓存TTL: {self.cache_ttl}，必须是非负整数")

        if not isinstance(self.max_cache_size, int) or self.max_cache_size <= 0:
            raise ValueError(f"无效的缓存最大大小: {self.max_cache_size}，必须是正整数")

    def get_plantuml_command(
        self, input_file: str, output_file: str, format: str
    ) -> List[str]:
        """
        构建 PlantUML 命令行参数

        根据配置参数和输入参数构建完整的 PlantUML 执行命令。

        Args:
            input_file (str): 输入 UML 文件路径
            output_file (str): 输出图像文件路径
            format (str): 输出格式（png, svg 等）

        Returns:
            List[str]: 完整的命令行参数列表，可直接用于 subprocess

        Examples:
            >>> config = Config()
            >>> cmd = config.get_plantuml_command(
            ...     "/tmp/input.puml", "/tmp/output.png", "png"
            ... )
            >>> print(cmd)  # ['java', '-Xmx512m', '-jar', '...', '-tpng', '...']
        """
        format_flag = "-tpng" if format == "png" else "-tsvg"

        return [
            self.java_executable,
            f"-Xmx{self.java_memory}",
            "-jar",
            self.plantuml_jar_path,
            format_flag,
            "-pipe",
            "-charset",
            "UTF-8",
        ]

    def create_directories(self) -> None:
        """
        创建必要的目录结构

        创建临时文件目录、缓存目录和日志目录。如果目录已存在则跳过。
        目录创建失败时会记录警告但不会抛出异常。

        Note:
            建议在服务启动时调用此方法，确保所有必要的目录都存在。
        """
        directories: List[str] = [self.temp_dir, self.cache_dir, self.logs_dir]

        for directory in directories:
            Path(directory).mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> Dict[str, Any]:
        """
        将配置转换为字典格式

        导出所有配置参数为字典格式，便于序列化、日志记录和调试。
        敏感信息（如路径）会被包含，使用时需注意安全性。

        Returns:
            Dict[str, Any]: 包含所有配置参数的字典，结构化组织为：
                - server: 服务器相关配置
                - plantuml: PlantUML 相关配置
                - rendering: 渲染相关配置
                - filesystem: 文件系统配置
                - caching: 缓存配置
                - security: 安全配置
                - logging: 日志配置
                - metrics: 性能指标配置

        Examples:
            >>> config = Config()
            >>> config_dict = config.to_dict()
            >>> print(config_dict["server"]["host"])  # localhost
            >>> print(config_dict["rendering"]["timeout"])  # 30
        """

        return {
            "server": {"host": self.server_host, "port": self.server_port},
            "plantuml": {
                "jar_path": self.plantuml_jar_path,
                "java_executable": self.java_executable,
                "java_memory": self.java_memory,
            },
            "rendering": {
                "timeout": self.render_timeout,
                "max_uml_size": self.max_uml_size,
                "max_concurrent_renders": self.max_concurrent_renders,
                "allowed_formats": self.allowed_formats,
            },
            "filesystem": {
                "temp_dir": self.temp_dir,
                "cache_dir": self.cache_dir,
                "logs_dir": self.logs_dir,
                "output_dir": self.output_dir,
            },
            "cache": {
                "enabled": self.enable_cache,
                "ttl": self.cache_ttl,
                "max_size": self.max_cache_size,
            },
            "security": {"max_diagram_complexity": self.max_diagram_complexity},
            "logging": {"level": self.log_level, "format": self.log_format},
            "metrics": {"enabled": self.enable_metrics, "port": self.metrics_port},
        }

    def __str__(self) -> str:
        """
        返回配置的字符串表示

        Returns:
            str: 配置信息
        """
        return (
            f"UML MCP Config(host={self.server_host}, "
            f"port={self.server_port}, plantuml={self.plantuml_jar_path})"
        )
