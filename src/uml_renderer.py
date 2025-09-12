#!/usr/bin/env python3
"""
UML 渲染器模块

核心渲染逻辑，负责调用 PlantUML 生成 UML 图表。
采用异步架构，支持并发控制、缓存机制和性能监控。

Author: UML MCP Team
Version: 1.0.0
"""

import asyncio
import hashlib
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, Any, AsyncGenerator

import aiofiles
import aiofiles.tempfile
from loguru import logger

from .config import Config
from .exceptions import (
    UMLRenderError,
    PlantUMLNotFoundError,
    RenderTimeoutError,
    ConcurrencyLimitError,
)
from .cache import RenderCache
from .metrics import RenderMetrics


class RenderSession:
    """
    渲染会话管理器

    管理单次渲染过程中的状态和资源。

    Attributes:
        start_time (float): 渲染开始时间
        session_id (str): 会话唯一标识
    """

    def __init__(self) -> None:
        """初始化渲染会话"""
        self.start_time = time.time()
        self.session_id = hashlib.md5(f"{time.time()}_{id(self)}".encode()).hexdigest()[
            :8
        ]
        logger.debug(f"渲染会话开始: {self.session_id}")

    def get_duration(self) -> float:
        """
        获取渲染持续时间

        Returns:
            float: 持续时间（秒）
        """
        return time.time() - self.start_time

    def __str__(self) -> str:
        return f"RenderSession({self.session_id})"


class UMLRenderer:
    """
    UML 渲染器

    负责调用 PlantUML 渲染 UML 图表，支持缓存、并发控制和性能监控。

    采用异步设计模式，提供以下核心功能：
    - 异步渲染处理，支持高并发
    - 智能缓存机制，提高性能
    - 资源管理和清理
    - 详细的性能指标收集
    - 优雅的错误处理和恢复

    Attributes:
        config (Config): 配置对象
        cache (Optional[RenderCache]): 缓存管理器
        metrics (Optional[RenderMetrics]): 性能指标收集器

    Examples:
        >>> config = Config()
        >>> renderer = UMLRenderer(config)
        >>> await renderer.initialize()
        >>> result = await renderer.render(uml_code, "png")
        >>> await renderer.cleanup()
    """

    def __init__(self, config: Config) -> None:
        """
        初始化 UML 渲染器

        Args:
            config (Config): 配置对象，包含所有渲染相关设置

        Note:
            初始化后需要调用 initialize() 方法完成异步初始化。
        """
        self.config = config
        self.cache = RenderCache(config) if config.enable_cache else None
        self.metrics = RenderMetrics() if config.enable_metrics else None
        self._concurrent_renders = 0
        self._render_lock = asyncio.Semaphore(config.max_concurrent_renders)
        self._initialized = False

        # 创建必要的目录
        config.create_directories()

    async def initialize(self) -> None:
        """
        异步初始化渲染器

        完成缓存系统初始化和 PlantUML 可用性检查。

        Raises:
            PlantUMLNotFoundError: PlantUML 不可用时抛出

        Note:
            此方法必须在使用渲染器前调用，且只需调用一次。
        """
        if not self._initialized:
            # 检查 PlantUML 可用性
            if not await self.check_plantuml_availability():
                raise PlantUMLNotFoundError(
                    "PlantUML 不可用，请检查配置",
                    jar_path=self.config.plantuml_jar_path,
                    java_path=self.config.java_executable,
                )

            # 初始化缓存系统
            if self.cache:
                await self.cache.initialize()

            logger.info("UML 渲染器初始化完成")
            self._initialized = True

    async def render(
        self, uml_code: str, output_format: str = "png", use_cache: bool = True
    ) -> bytes:
        """
        渲染 UML 图表

        Args:
            uml_code (str): UML DSL 代码，必须是有效的 PlantUML 语法
            output_format (str): 输出格式 (png, svg, pdf 等)，默认为 png
            use_cache (bool): 是否使用缓存，默认为 True

        Returns:
            bytes: 渲染结果的二进制数据

        Raises:
            UMLRenderError: 渲染失败时抛出
            ConcurrencyLimitError: 超过并发限制时抛出
            RenderTimeoutError: 渲染超时时抛出
            PlantUMLNotFoundError: PlantUML 不可用时抛出

        Examples:
            >>> renderer = UMLRenderer(config)
            >>> await renderer.initialize()
            >>> result = await renderer.render("@startuml\nA -> B\n@enduml")
            >>> print(f"渲染结果大小: {len(result)} 字节")

        Note:
            - 此方法是线程安全的，支持并发调用
            - 使用信号量控制并发数量，避免资源耗尽
            - 自动处理缓存的读取和写入
        """
        if not self._initialized:
            raise RuntimeError("渲染器未初始化，请先调用 initialize()")

        # 生成缓存键
        cache_key = self._generate_cache_key(uml_code, output_format)

        # 尝试从缓存获取
        if use_cache and self.cache:
            cached_result = await self.cache.get(cache_key)
            if cached_result:
                logger.info(f"缓存命中: {cache_key[:16]}...")
                if self.metrics:
                    await self.metrics.record_cache_hit()
                return cached_result

        # 使用上下文管理器处理渲染过程
        async with self._render_context() as render_session:
            try:
                # 执行渲染
                result = await self._render_internal(uml_code, output_format)

                # 保存到缓存
                if use_cache and self.cache:
                    await self.cache.set(cache_key, result)

                # 记录指标
                render_time = render_session.get_duration()
                if self.metrics:
                    await self.metrics.record_render(
                        format=output_format,
                        duration=render_time,
                        size=len(result),
                        cache_hit=False,
                    )

                logger.info(
                    f"渲染完成: 格式={output_format}, "
                    f"大小={len(result)}字节, "
                    f"耗时={render_time:.2f}秒"
                )

                return result

            except Exception as e:
                # 记录错误指标
                if self.metrics:
                    await self.metrics.record_error(str(type(e).__name__))
                raise

    @asynccontextmanager
    async def _render_context(self) -> AsyncGenerator["RenderSession", None]:
        """
        渲染上下文管理器

        管理渲染过程中的资源分配、并发控制和清理工作。

        Yields:
            RenderSession: 渲染会话对象

        Raises:
            ConcurrencyLimitError: 超过并发限制时抛出
        """
        # 检查并发限制
        if self._concurrent_renders >= self.config.max_concurrent_renders:
            raise ConcurrencyLimitError(
                "并发渲染请求超过限制",
                current_count=self._concurrent_renders,
                max_count=self.config.max_concurrent_renders,
            )

        # 获取渲染锁
        async with self._render_lock:
            self._concurrent_renders += 1
            session = RenderSession()

            try:
                yield session
            finally:
                self._concurrent_renders -= 1

    async def _render_internal(self, uml_code: str, output_format: str) -> bytes:
        """
        内部渲染实现

        使用 PlantUML 命令行工具执行实际的渲染操作。

        Args:
            uml_code (str): PlantUML DSL 代码
            output_format (str): 输出格式 (png, svg, pdf 等)

        Returns:
            bytes: 渲染结果的二进制数据

        Raises:
            UMLRenderError: 渲染失败时抛出
            RenderTimeoutError: 渲染超时时抛出

        Note:
            - 使用临时文件避免内存溢出
            - 支持超时控制和进程管理
            - 自动清理临时资源
        """
        # 使用异步临时文件处理
        async with aiofiles.tempfile.NamedTemporaryFile(
            mode="w", suffix=".puml", encoding="utf-8", delete=False
        ) as temp_file:
            # 异步写入UML代码
            await temp_file.write(uml_code)
            await temp_file.flush()
            temp_file_path = temp_file.name

        try:
            # 构建 PlantUML 命令
            command = self.config.get_plantuml_command(
                input_file=str(temp_file_path),
                output_file="",  # 使用管道输出
                format=output_format,
            )

            logger.debug(f"执行命令: {' '.join(command)}")

            # 执行渲染过程
            result = await self._execute_plantuml_command(command, uml_code)
            return result

        finally:
            # 异步清理临时文件
            try:
                Path(str(temp_file_path)).unlink()
            except OSError as e:
                logger.warning(f"清理临时文件失败: {e}")

    async def _execute_plantuml_command(self, command: list, uml_code: str) -> bytes:
        """
        执行 PlantUML 命令

        Args:
            command (list): PlantUML 命令参数列表
            uml_code (str): UML 代码（用于错误报告）

        Returns:
            bytes: 渲染结果

        Raises:
            UMLRenderError: 渲染失败
            RenderTimeoutError: 渲染超时
        """
        # 创建子进程
        process = await asyncio.create_subprocess_exec(
            *command,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            # 发送输入并等待结果
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=uml_code.encode("utf-8")),
                timeout=self.config.render_timeout,
            )

            # 检查返回码
            if process.returncode != 0:
                error_msg = stderr.decode("utf-8", errors="ignore")
                logger.error(f"PlantUML 渲染失败: {error_msg}")
                raise UMLRenderError(
                    f"PlantUML 渲染失败 (返回码: {process.returncode})",
                    uml_code=uml_code,
                    stderr=error_msg,
                )

            # 检查输出
            if not stdout:
                raise UMLRenderError("PlantUML 没有生成输出", uml_code=uml_code)

            return stdout

        except asyncio.TimeoutError:
            # 优雅地终止进程
            await self._terminate_process_gracefully(process)
            raise RenderTimeoutError(
                f"渲染超时 ({self.config.render_timeout} 秒)",
                timeout=self.config.render_timeout,
            )

    async def _terminate_process_gracefully(
        self, process: asyncio.subprocess.Process
    ) -> None:
        """
        优雅地终止进程

        Args:
            process: 要终止的进程
        """
        try:
            # 首先尝试温和终止
            process.terminate()
            await asyncio.wait_for(process.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            # 如果温和终止失败，强制杀死进程
            logger.warning("进程未响应终止信号，强制杀死")
            process.kill()
            await process.wait()

    async def validate_syntax(self, uml_code: str) -> bool:
        """
        验证 UML 语法

        Args:
            uml_code (str): UML DSL 代码

        Returns:
            bool: 语法是否有效

        Raises:
            UMLRenderError: 语法错误
        """
        try:
            # 尝试渲染为 PNG 格式进行语法验证
            await self._render_internal(uml_code, "png")
            return True
        except UMLRenderError:
            raise
        except Exception as e:
            raise UMLRenderError(f"语法验证失败: {str(e)}")

    def validate_uml_syntax(self, uml_code: str) -> bool:
        """
        同步版本的UML语法验证（为了兼容测试）

        Args:
            uml_code (str): UML 代码

        Returns:
            bool: 语法是否有效

        Raises:
            UMLValidationError: 当UML语法无效时
        """
        from .exceptions import UMLValidationError

        # 基本语法检查
        if not uml_code.strip():
            raise UMLValidationError("UML代码不能为空")

        # 检查是否包含必要的标记
        if "@startuml" not in uml_code or "@enduml" not in uml_code:
            raise UMLValidationError("UML代码必须包含@startuml和@enduml标记")

        return True

    async def check_plantuml_availability(self) -> bool:
        """
        检查 PlantUML 是否可用

        Returns:
            bool: PlantUML 是否可用
        """
        try:
            # 检查 JAR 文件是否存在
            if not Path(self.config.plantuml_jar_path).exists():
                logger.error(f"PlantUML JAR 文件不存在: {self.config.plantuml_jar_path}")
                return False

            # 检查 Java 是否可用
            process = await asyncio.create_subprocess_exec(
                self.config.java_executable,
                "-version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"Java 不可用: {stderr.decode()}")
                return False

            # 测试 PlantUML
            test_uml = "@startuml\nAlice -> Bob: Test\n@enduml"

            command = self.config.get_plantuml_command(
                input_file="", output_file="", format="png"
            )

            process = await asyncio.create_subprocess_exec(
                *command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=test_uml.encode("utf-8")), timeout=10.0
            )

            if process.returncode != 0:
                logger.error(f"PlantUML 测试失败: {stderr.decode()}")
                return False

            logger.info("PlantUML 可用性检查通过")
            return True

        except FileNotFoundError as e:
            logger.error(f"PlantUML 文件未找到: {str(e)}")
            raise PlantUMLNotFoundError(f"PlantUML 不可用: {str(e)}")
        except Exception as e:
            logger.error(f"PlantUML 可用性检查失败: {str(e)}")
            return False

    async def get_plantuml_version(self) -> str:
        """
        获取 PlantUML 版本信息

        Returns:
            str: 版本信息
        """
        try:
            command = [
                self.config.java_executable,
                "-jar",
                self.config.plantuml_jar_path,
                "-version",
            ]

            process = await asyncio.create_subprocess_exec(
                *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0:
                version_info = stdout.decode("utf-8", errors="ignore")
                # 提取版本号
                for line in version_info.split("\n"):
                    if "PlantUML" in line and "version" in line.lower():
                        return line.strip()
                return version_info.split("\n")[0] if version_info else "未知版本"
            else:
                return "版本获取失败"

        except Exception as e:
            logger.warning(f"获取 PlantUML 版本失败: {str(e)}")
            return "版本获取失败"

    def _generate_cache_key(self, uml_code: str, output_format: str) -> str:
        """
        生成缓存键

        Args:
            uml_code (str): UML 代码
            output_format (str): 输出格式

        Returns:
            str: 缓存键
        """
        content = f"{uml_code}:{output_format}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    async def cleanup(self) -> None:
        """
        清理资源
        """
        logger.info("清理 UML 渲染器资源...")

        # 清理缓存
        if self.cache:
            await self.cache.cleanup()

        # 清理临时文件
        temp_dir = Path(self.config.temp_dir)
        if temp_dir.exists():
            try:
                import shutil

                shutil.rmtree(temp_dir)
                logger.info(f"已清理临时目录: {temp_dir}")
            except Exception as e:
                logger.warning(f"清理临时目录失败: {str(e)}")

        logger.info("UML 渲染器资源清理完成")

    async def get_stats(self) -> Dict[str, Any]:
        """
        获取渲染器统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        stats = {
            "concurrent_renders": self._concurrent_renders,
            "max_concurrent_renders": self.config.max_concurrent_renders,
            "cache_enabled": self.config.enable_cache,
            "metrics_enabled": self.config.enable_metrics,
        }

        if self.cache:
            cache_stats = self.cache.get_stats()
            stats.update(cache_stats if isinstance(cache_stats, dict) else {})

        if self.metrics:
            render_metrics = await self.metrics.get_stats()
            stats.update(render_metrics if isinstance(render_metrics, dict) else {})

        return stats

    def get_metrics(self) -> Dict[str, Any]:
        """
        获取性能指标

        Returns:
            Dict[str, Any]: 性能指标数据
        """
        if self.metrics:
            # 返回基本的指标数据结构
            return {
                'total_renders': getattr(self.metrics, 'total_renders', 0),
                'successful_renders': getattr(self.metrics, 'successful_renders', 0),
                'failed_renders': getattr(self.metrics, 'failed_renders', 0),
                'cache_hits': getattr(self.metrics, 'cache_hits', 0),
                'cache_misses': getattr(self.metrics, 'cache_misses', 0),
                'average_render_time': getattr(self.metrics, 'average_render_time', 0.0)
            }
        return {
            'total_renders': 0,
            'successful_renders': 0,
            'failed_renders': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'average_render_time': 0.0
        }

    def check_plantuml_availability_sync(self) -> bool:
        """
        同步版本的PlantUML可用性检查（为了兼容测试）

        Returns:
            bool: PlantUML 是否可用

        Raises:
            PlantUMLNotFoundError: 当PlantUML不可用时
        """
        import subprocess

        try:
            # 检查 JAR 文件是否存在
            if not Path(self.config.plantuml_jar_path).exists():
                logger.error(
                    f"PlantUML JAR 文件不存在: {self.config.plantuml_jar_path}"
                )
                raise PlantUMLNotFoundError(
                    f"PlantUML JAR 文件不存在: {self.config.plantuml_jar_path}"
                )

            # 检查 Java 是否可用（这里会被测试mock）
            subprocess.run(
                [self.config.java_executable, "-version"],
                capture_output=True,
                check=True
            )

            return True

        except FileNotFoundError as e:
            logger.error(f"PlantUML 文件未找到: {str(e)}")
            raise PlantUMLNotFoundError(f"PlantUML 不可用: {str(e)}")
        except Exception as e:
            logger.error(f"PlantUML 可用性检查失败: {str(e)}")
            raise PlantUMLNotFoundError(f"PlantUML 不可用: {str(e)}")
