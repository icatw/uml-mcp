#!/usr/bin/env python3
"""
异常处理模块

定义 UML MCP 渲染服务的自定义异常类。
提供结构化的错误处理和详细的错误信息。

Author: UML MCP Team
Version: 1.0.0
"""

from typing import Optional, Dict, Any, Callable, Awaitable


class UMLMCPError(Exception):
    """
    UML MCP 服务基础异常类

    所有 UML MCP 相关异常的基类，提供统一的错误处理接口。

    Attributes:
        message (str): 错误消息
        error_code (Optional[str]): 错误代码，用于程序化处理
        details (Optional[Dict[str, Any]]): 详细错误信息

    Examples:
        >>> raise UMLMCPError("基础错误", error_code="UML_001")
        >>> try:
        ...     # some operation
        ... except UMLMCPError as e:
        ...     print(f"错误: {e.message}, 代码: {e.error_code}")
    """

    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        初始化异常

        Args:
            message (str): 错误消息
            error_code (Optional[str]): 错误代码，便于程序化处理
            details (Optional[Dict[str, Any]]): 详细错误信息字典
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "UNKNOWN_ERROR"
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        将异常转换为字典格式

        Returns:
            Dict[str, Any]: 异常信息字典，包含错误代码、消息和详细信息
        """
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(UMLMCPError):
    """
    输入验证异常

    当输入参数不符合要求时抛出，包括 UML 语法错误、参数格式错误等。

    Examples:
        >>> raise ValidationError(
        ...     "UML 代码格式无效",
        ...     field="uml_code",
        ...     value="invalid syntax"
        ... )
    """

    def __init__(
        self, message: str, field: Optional[str] = None, value: Optional[str] = None
    ) -> None:
        """
        初始化验证异常

        Args:
            message (str): 错误消息
            field (Optional[str]): 验证失败的字段名
            value (Optional[str]): 验证失败的值
        """
        super().__init__(message, "VALIDATION_ERROR")
        if field:
            self.details["field"] = field
        if value:
            self.details["value"] = value


class UMLRenderError(UMLMCPError):
    """
    UML 渲染异常

    当 PlantUML 渲染过程失败时抛出，包括 PlantUML 执行失败、语法错误等。

    Examples:
        >>> raise UMLRenderError(
        ...     "PlantUML 渲染失败",
        ...     uml_code="@startuml\n...",
        ...     stderr="Syntax error at line 5"
        ... )
    """

    def __init__(
        self, message: str, uml_code: Optional[str] = None, stderr: Optional[str] = None
    ) -> None:
        """
        初始化渲染异常

        Args:
            message (str): 错误消息
            uml_code (Optional[str]): 导致错误的 UML 代码
            stderr (Optional[str]): PlantUML 的错误输出
        """
        super().__init__(message, "RENDER_ERROR")
        if uml_code:
            self.details["uml_code_length"] = len(uml_code)
        if stderr:
            self.details["stderr"] = stderr


class PlantUMLNotFoundError(UMLMCPError):
    """
    PlantUML 不可用异常

    当找不到 PlantUML JAR 文件或 Java 运行时时抛出。
    """

    def __init__(
        self,
        message: str,
        jar_path: Optional[str] = None,
        java_path: Optional[str] = None,
    ) -> None:
        """
        初始化 PlantUML 不可用异常

        Args:
            message (str): 错误消息
            jar_path (Optional[str]): PlantUML JAR 文件路径
            java_path (Optional[str]): Java 运行时路径
        """
        super().__init__(message, "PLANTUML_NOT_FOUND")
        if jar_path:
            self.details["jar_path"] = jar_path
        if java_path:
            self.details["java_path"] = java_path


class RenderTimeoutError(UMLMCPError):
    """
    渲染超时异常

    当渲染过程超过指定时间限制时抛出。
    """

    def __init__(self, message: str, timeout: Optional[int] = None) -> None:
        """
        初始化渲染超时异常

        Args:
            message (str): 错误消息
            timeout (Optional[int]): 超时时间（秒）
        """
        super().__init__(message, "RENDER_TIMEOUT")
        if timeout:
            self.details["timeout_seconds"] = timeout


# 为了向后兼容，添加别名
UMLTimeoutError = RenderTimeoutError
UMLValidationError = ValidationError


class FileSizeExceededError(ValidationError):
    """
    文件大小超限异常

    当输入的 UML 代码超过大小限制时抛出。
    """

    def __init__(self, message: str, size: int, max_size: int) -> None:
        """
        初始化文件大小超限异常

        Args:
            message (str): 错误消息
            size (int): 实际文件大小
            max_size (int): 最大允许大小
        """
        super().__init__(message, "FILE_SIZE_EXCEEDED")
        self.details.update({"actual_size": size, "max_size": max_size})


class UnsupportedFormatError(ValidationError):
    """
    不支持的格式异常

    当请求的输出格式不被支持时抛出。
    """

    def __init__(self, message: str, format: str, supported_formats: list) -> None:
        """
        初始化不支持格式异常

        Args:
            message (str): 错误消息
            format (str): 请求的格式
            supported_formats (list): 支持的格式列表
        """
        super().__init__(message, "UNSUPPORTED_FORMAT")
        self.details.update(
            {"requested_format": format, "supported_formats": supported_formats}
        )


class InvalidUMLSyntaxError(ValidationError):
    """
    无效 UML 语法异常

    当 UML 代码语法不正确时抛出。
    """

    def __init__(
        self,
        message: str,
        line_number: Optional[int] = None,
        syntax_error: Optional[str] = None,
    ) -> None:
        """
        初始化无效 UML 语法异常

        Args:
            message (str): 错误消息
            line_number (Optional[int]): 错误行号
            syntax_error (Optional[str]): 具体语法错误信息
        """
        super().__init__(message, "INVALID_UML_SYNTAX")
        if line_number:
            self.details["line_number"] = line_number
        if syntax_error:
            self.details["syntax_error"] = syntax_error


class ConcurrencyLimitError(UMLMCPError):
    """
    并发限制异常

    当并发渲染请求超过限制时抛出。
    """

    def __init__(self, message: str, current_count: int, max_count: int) -> None:
        """
        初始化并发限制异常

        Args:
            message (str): 错误消息
            current_count (int): 当前并发数
            max_count (int): 最大并发数
        """
        super().__init__(message, "CONCURRENCY_LIMIT_EXCEEDED")
        self.details.update(
            {
                "current_concurrent_renders": current_count,
                "max_concurrent_renders": max_count,
            }
        )


class CacheError(UMLMCPError):
    """
    缓存操作异常

    当缓存读写操作失败时抛出。
    """

    def __init__(self, message: str, operation: Optional[str] = None) -> None:
        """
        初始化缓存操作异常

        Args:
            message (str): 错误消息
            operation (Optional[str]): 失败的缓存操作类型
        """
        super().__init__(message, "CACHE_ERROR")
        if operation:
            self.details["operation"] = operation


class ConfigurationError(UMLMCPError):
    """
    配置错误异常

    当服务配置不正确时抛出。
    """

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        config_value: Optional[str] = None,
    ) -> None:
        """
        初始化配置错误异常

        Args:
            message (str): 错误消息
            config_key (Optional[str]): 配置项键名
            config_value (Optional[str]): 配置项值
        """
        super().__init__(message, "CONFIGURATION_ERROR")
        if config_key:
            self.details["config_key"] = config_key
        if config_value:
            self.details["config_value"] = config_value


class ResourceExhaustionError(UMLMCPError):
    """
    资源耗尽异常

    当系统资源不足时抛出。
    """

    def __init__(self, message: str, resource_type: Optional[str] = None) -> None:
        """
        初始化资源耗尽异常

        Args:
            message (str): 错误消息
            resource_type (Optional[str]): 耗尽的资源类型
        """
        super().__init__(message, "RESOURCE_EXHAUSTION")
        if resource_type:
            self.details["resource_type"] = resource_type


def handle_exception(
    func: Callable[..., Awaitable[Dict[str, Any]]]
) -> Callable[..., Awaitable[Dict[str, Any]]]:
    """
    异常处理装饰器

    统一处理函数中的异常，转换为标准的错误响应格式。

    Args:
        func: 要装饰的异步函数

    Returns:
        装饰后的异步函数，返回统一的错误响应格式

    Examples:
        >>> @handle_exception
        ... async def render_uml(code: str):
        ...     # 渲染逻辑
        ...     pass
    """

    async def wrapper(*args: Any, **kwargs: Any) -> Dict[str, Any]:
        try:
            return await func(*args, **kwargs)
        except UMLMCPError as e:
            # UML MCP 自定义异常，直接返回结构化错误信息
            return {"success": False, "error": e.to_dict()}
        except Exception as e:
            # 未知异常，包装为通用错误
            error = UMLMCPError(message=f"未知错误: {str(e)}", error_code="INTERNAL_ERROR")
            return {"success": False, "error": error.to_dict()}

    return wrapper
