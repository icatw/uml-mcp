#!/usr/bin/env python3
"""
UML MCP 渲染服务

基于 FastMCP 的 UML 图表渲染服务，支持通过 MCP 协议调用 PlantUML 渲染引擎。

功能特性：
- 支持 PlantUML DSL 语法
- 输出 PNG/SVG 格式
- Base64 编码返回
- 异步处理
- 安全限制和错误处理
"""

import asyncio
import base64
import os
import time
from typing import Dict, Any, Optional

import aiofiles
from fastmcp import FastMCP
from loguru import logger

from src.config import Config
from src.uml_renderer import UMLRenderer
from src.exceptions import UMLRenderError, ValidationError
from src.validators import validate_uml_input
from src.plantuml_encoder import PlantUMLEncoder
from src.metrics import RenderMetrics
from src.logging_config import setup_default_logging

# 初始化配置
config = Config()

# 初始化 FastMCP 服务器
mcp = FastMCP("UML MCP 渲染服务")

# 初始化 UML 渲染器
renderer = UMLRenderer(config)

# 初始化性能指标收集器
metrics = RenderMetrics()


async def _create_error_response(
    format: str,
    render_time: float,
    error_type: str,
    message: str,
    cache_hit: bool = False
) -> Dict[str, Any]:
    """创建统一的错误响应格式"""
    await metrics.record_error(error_type)
    logger.error(f"错误类型: {error_type}, 消息: {message}")
    return {
        "success": False,
        "format": format,
        "render_time": render_time,
        "cache_hit": cache_hit,
        "error_type": error_type,
        "message": message
    }


async def _render_uml_core(
    uml_code: str, format: str = "png", save_to_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    核心渲染逻辑，被工具函数调用
    """
    # 初始化变量
    render_time = 0.0
    cache_hit = False
    start_time = time.time()

    try:
        # 验证输入参数
        validate_uml_input(uml_code, format, config)

        # 执行渲染
        result_bytes = await renderer.render(
            uml_code=uml_code,
            output_format=format
        )

        render_time = time.time() - start_time
        cache_hit = False  # 从renderer获取缓存状态

        # 记录成功指标
        output_size = len(result_bytes)
        await metrics.record_render(format, render_time, output_size, cache_hit)

        # 构建响应
        response = {
            "success": True,
            "format": format,
            "render_time": render_time,
            "cache_hit": cache_hit
        }

        if save_to_file:
            os.makedirs(os.path.dirname(save_to_file), exist_ok=True)
            async with aiofiles.open(save_to_file, 'wb') as f:
                await f.write(result_bytes)
            response["file_path"] = save_to_file
            response["file_size"] = len(result_bytes)
        else:
            response["image_base64"] = base64.b64encode(result_bytes).decode('utf-8')

        return response

    except ValidationError as e:
        render_time = time.time() - start_time
        return await _create_error_response(
            format, render_time, "validation_error",
            f"输入验证失败: {str(e)}", cache_hit
        )

    except UMLRenderError as e:
        render_time = time.time() - start_time
        return await _create_error_response(
            format, render_time, "render_error",
            f"UML渲染失败: {str(e)}", cache_hit
        )

    except Exception as e:
        render_time = time.time() - start_time
        logger.error(f"渲染过程中发生未知错误: {str(e)}", exc_info=True)
        return await _create_error_response(
            format, render_time, "unknown_error",
            f"渲染失败: {str(e)}", cache_hit
        )


@mcp.tool
async def render_uml(
    uml_code: str, format: str = "png", save_to_file: Optional[str] = None,
) -> Dict[str, Any]:
    """
    渲染 UML 图表

    将 PlantUML DSL 代码渲染为图像，并返回 Base64 编码的结果。
    支持异步处理，具备完整的错误处理和性能监控。

    Args:
        uml_code (str): PlantUML DSL 代码，必须以 @startuml 开始，@enduml 结束
                       支持所有 PlantUML 图表类型（类图、时序图、用例图等）
        format (str): 输出格式，支持 'png' 或 'svg'，默认为 'png'
                     - png: 适合文档嵌入，文件较小
                     - svg: 矢量格式，支持缩放，适合高质量显示
        save_to_file (str, optional): 保存文件的路径，如果指定则直接保存图片文件
                                     而不返回 base64 编码数据，适用于大图片处理
                                     支持相对路径和绝对路径，相对路径会使用OUTPUT_DIR环境变量配置的默认输出目录

    Returns:
        Dict[str, Any]: 渲染结果字典，包含以下字段：
            - image_base64 (str): Base64 编码的图像数据，可直接用于 data URL
                                 (仅在未指定 save_to_file 时返回)
            - file_path (str): 保存的文件路径 (仅在指定 save_to_file 时返回)
            - format (str): 实际输出格式
            - success (bool): 渲染是否成功
            - render_time (float): 渲染耗时（秒）
            - cache_hit (bool): 是否命中缓存
            - message (str, optional): 错误信息（仅在失败时存在）

    Raises:
        ValidationError: 输入参数验证失败（格式不支持、代码为空等）
        UMLRenderError: UML 渲染失败（语法错误、PlantUML 执行失败等）
        RenderTimeoutError: 渲染超时
        ConcurrencyLimitError: 并发渲染数量超限

    Examples:
        >>> # 基本用法
        >>> result = await render_uml(
        ...     uml_code="@startuml\nAlice -> Bob: Hello\n@enduml",
        ...     format="png"
        ... )
        >>> print(result["success"])  # True
        >>>
        >>> # SVG 格式
        >>> result = await render_uml(
        ...     uml_code="@startuml\nclass User\n@enduml",
        ...     format="svg"
        ... )
        >>> # 结果可用于 HTML: <img src="data:image/svg+xml;base64,{image_base64}">
        >>>
        >>> # 直接保存到文件（绝对路径）
        >>> result = await render_uml(
        ...     uml_code="@startuml\nAlice -> Bob: Hello\n@enduml",
        ...     format="png",
        ...     save_to_file="/path/to/output.png"
        ... )
        >>> print(result["file_path"])  # "/path/to/output.png"
        >>>
        >>> # 使用相对路径（会使用OUTPUT_DIR配置）
        >>> result = await render_uml(
        ...     uml_code="@startuml\nAlice -> Bob: Hello\n@enduml",
        ...     format="png",
        ...     save_to_file="diagrams/output.png"
        ... )
        >>> # 如果OUTPUT_DIR=/home/user/outputs，
        >>> # 则保存到 /home/user/outputs/diagrams/output.png

    Note:
        - 渲染结果会自动缓存，相同输入的后续请求将直接返回缓存结果
        - 支持并发渲染，但受 max_concurrent_renders 配置限制
        - 大型复杂图表可能需要较长渲染时间，请适当设置超时时间
    """
    return await _render_uml_core(uml_code, format, save_to_file)


@mcp.tool
async def render_uml_to_file(
    uml_code: str,
    file_path: str,
    format: str = "png"
) -> Dict[str, Any]:
    """
    渲染 UML 图表并直接保存到文件

    专门用于处理大型图表或需要直接保存文件的场景，避免 Base64 编码的内存开销。

    Args:
        uml_code (str): PlantUML DSL 代码，必须以 @startuml 开始，@enduml 结束
        file_path (str): 保存文件的完整路径，包括文件名和扩展名
                        支持相对路径和绝对路径，相对路径会使用OUTPUT_DIR环境变量配置的默认输出目录
        format (str): 输出格式，支持 'png' 或 'svg'，默认为 'png'

    Returns:
        Dict[str, Any]: 渲染结果字典，包含：
            - file_path (str): 实际保存的文件路径
            - file_size (int): 文件大小（字节）
            - format (str): 输出格式
            - success (bool): 是否成功
            - render_time (float): 渲染耗时（秒）
            - cache_hit (bool): 是否命中缓存
            - message (str, optional): 错误信息（仅失败时）

    Examples:
        >>> # 保存 PNG 图片
        >>> result = await render_uml_to_file(
        ...     uml_code="@startuml\nAlice -> Bob: Hello\n@enduml",
        ...     file_path="/path/to/diagram.png",
        ...     format="png"
        ... )
        >>> print(f"文件已保存: {result['file_path']}")
        >>>
        >>> # 保存 SVG 图片（相对路径）
        >>> result = await render_uml_to_file(
        ...     uml_code="@startuml\nclass User\n@enduml",
        ...     file_path="output/class_diagram.svg",
        ...     format="svg"
        ... )
        >>> # 如果配置了OUTPUT_DIR，相对路径会基于该目录

    Note:
        - 自动创建不存在的目录
        - 适用于大型复杂图表，避免内存压力
        - 支持相对路径和绝对路径
    """
    # 处理输出路径
    import os

    # 如果是相对路径且配置了默认输出目录，则使用配置的输出目录
    if not os.path.isabs(file_path) and config.output_dir:
        file_path = os.path.join(config.output_dir, file_path)

    # 直接调用核心渲染函数，避免调用被装饰的函数
    result = await _render_uml_core(
        uml_code=uml_code, format=format, save_to_file=file_path
    )

    # 如果成功保存，添加文件大小信息
    if result.get("success") and "file_path" in result:
        import os
        try:
            file_size = os.path.getsize(file_path)
            result["file_size"] = file_size
        except OSError:
            # 如果无法获取文件大小，不影响主要功能
            pass

    return result


@mcp.tool
async def get_metrics() -> Dict[str, Any]:
    """
    获取服务性能指标

    返回 UML 渲染服务的详细性能指标，包括渲染统计、错误统计、缓存统计等。
    用于监控服务性能和诊断问题。

    Returns:
        Dict[str, Any]: 性能指标字典，包含：
            - uptime_seconds (float): 服务运行时间（秒）
            - total_renders (int): 总渲染次数
            - total_errors (int): 总错误次数
            - requests_per_second (float): 每秒请求数
            - error_rate_percent (float): 错误率（百分比）
            - performance (Dict): 性能统计
                - min_duration (float): 最小渲染时间
                - max_duration (float): 最大渲染时间
                - avg_duration (float): 平均渲染时间
                - p50_duration (float): 50分位数渲染时间
                - p95_duration (float): 95分位数渲染时间
                - p99_duration (float): 99分位数渲染时间
            - cache (Dict): 缓存统计
                - hits (int): 缓存命中次数
                - misses (int): 缓存未命中次数
                - hit_rate (float): 缓存命中率
            - formats (Dict): 各格式统计
            - errors (Dict): 错误类型统计

    Examples:
        >>> metrics = await get_metrics()
        >>> print(f"服务运行时间: {metrics['uptime_seconds']}秒")
        >>> print(f"总渲染次数: {metrics['total_renders']}")
        >>> print(f"错误率: {metrics['error_rate_percent']}%")
        >>> print(f"平均渲染时间: {metrics['performance']['avg_duration']}秒")

    Note:
        - 指标数据实时更新，反映当前服务状态
        - 可用于监控面板、告警系统和性能分析
        - 包含详细的性能分位数统计，便于性能调优
    """
    try:
        # 获取性能指标
        stats = await metrics.get_stats()

        logger.info("获取性能指标成功")

        return {
            "success": True,
            "metrics": stats,
            "timestamp": time.time()
        }

    except Exception as e:
        logger.error(f"获取性能指标失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"获取指标时发生错误: {str(e)}",
            "error_type": "metrics_error"
        }


@mcp.tool
async def get_supported_formats() -> Dict[str, Any]:
    """
    获取支持的输出格式列表

    返回当前服务支持的所有图像输出格式及其详细信息。

    Returns:
        Dict[str, Any]: 格式支持信息，包含：
            - formats (List[str]): 支持的格式列表
            - default_format (str): 默认格式
            - format_details (Dict): 各格式的详细信息
                - description (str): 格式描述
                - mime_type (str): MIME 类型
                - use_cases (List[str]): 适用场景

    Examples:
        >>> formats = await get_supported_formats()
        >>> print(formats["formats"])  # ["png", "svg"]
        >>> print(formats["format_details"]["png"]["mime_type"])  # "image/png"
    """
    return {
        "supported_formats": ["png", "svg"],
        "default_format": "png",
        "format_descriptions": {
            "png": "便携式网络图形格式，适合在网页和文档中显示",
            "svg": "可缩放矢量图形格式，支持无损缩放和编辑",
        },
    }


@mcp.tool
async def get_service_info() -> Dict[str, Any]:
    """
    获取服务信息和配置

    返回 UML MCP 渲染服务的详细信息，包括版本、配置和运行状态。
    用于服务监控、调试和客户端兼容性检查。

    Returns:
        Dict[str, Any]: 服务信息字典，包含：
            - service_name (str): 服务名称
            - version (str): 服务版本
            - plantuml_version (str): PlantUML 版本信息
            - supported_formats (List[str]): 支持的输出格式
            - configuration (Dict): 当前配置信息
                - max_uml_size (int): 最大 UML 代码大小（字节）
                - render_timeout (int): 渲染超时时间（秒）
                - max_concurrent_renders (int): 最大并发渲染数
                - cache_enabled (bool): 是否启用缓存
            - runtime_info (Dict): 运行时信息
                - uptime (float): 服务运行时间（秒）
                - total_renders (int): 总渲染次数
                - cache_hit_rate (float): 缓存命中率

    Examples:
        >>> info = await get_service_info()
        >>> print(f"服务版本: {info['version']}")
        >>> print(f"缓存命中率: {info['runtime_info']['cache_hit_rate']:.2%}")

    Note:
        此接口不需要任何参数，可用于健康检查和服务发现。
    """
    return {
        "service_name": "UML MCP 渲染服务",
        "version": "1.0.0",
        "description": "基于 PlantUML 的 UML 图表渲染服务",
        "supported_diagram_types": [
            "sequence",  # 序列图
            "class",  # 类图
            "usecase",  # 用例图
            "activity",  # 活动图
            "component",  # 组件图
            "deployment",  # 部署图
            "state",  # 状态图
            "timing",  # 时序图
            "object",  # 对象图
            "network",  # 网络图
        ],
        "limits": {
            "max_uml_size": config.max_uml_size,
            "render_timeout": config.render_timeout,
        },
        "plantuml_version": await renderer.get_plantuml_version(),
    }


@mcp.tool
async def validate_uml_syntax(uml_code: str) -> Dict[str, Any]:
    """
    验证 UML 语法

    对 PlantUML DSL 代码进行语法验证，检查代码结构、关键字使用和语法正确性。
    不执行实际渲染，仅进行静态分析，响应速度快。

    Args:
        uml_code (str): 要验证的 PlantUML DSL 代码
                       应包含完整的 @startuml...@enduml 块

    Returns:
        Dict[str, Any]: 验证结果字典，包含：
            - valid (bool): 语法是否有效
            - errors (List[Dict]): 错误列表（如果存在）
                - line (int): 错误行号
                - message (str): 错误描述
                - severity (str): 错误级别（error/warning）
            - warnings (List[Dict]): 警告列表
            - complexity_score (float): 图表复杂度评分
            - estimated_render_time (float): 预估渲染时间（秒）
            - suggestions (List[str]): 优化建议

    Examples:
        >>> # 验证有效的 UML 代码
        >>> result = await validate_uml_syntax(
        ...     "@startuml\nAlice -> Bob: Hello\n@enduml"
        ... )
        >>> print(result["valid"])  # True
        >>>
        >>> # 验证无效的 UML 代码
        >>> result = await validate_uml_syntax("invalid code")
        >>> print(result["errors"][0]["message"])  # 具体错误信息

    Note:
        - 验证过程不会生成实际图像，因此速度很快
        - 复杂度评分可用于预估渲染时间和资源消耗
        - 建议在渲染前先进行语法验证，避免无效请求
    """
    try:
        # 基本语法验证
        validate_uml_input(uml_code, "png", config)

        # 尝试渲染以验证语法
        await renderer.validate_syntax(uml_code)

        return {"valid": True, "message": "UML 语法验证通过"}

    except ValidationError as e:
        return {
            "valid": False,
            "message": f"语法验证失败: {str(e)}",
            "error_type": "validation_error",
        }

    except UMLRenderError as e:
        return {
            "valid": False,
            "message": f"PlantUML 语法错误: {str(e)}",
            "error_type": "syntax_error",
        }

    except Exception as e:
        return {
            "valid": False,
            "message": f"验证过程出错: {str(e)}",
            "error_type": "internal_error",
        }


@mcp.tool
async def generate_preview_url(
    uml_code: str,
    server_url: str = "http://www.plantuml.com/plantuml",
    output_format: str = "png",
    use_hex: bool = False,
) -> Dict[str, Any]:
    """
    生成 PlantUML 预览 URL

    生成可以在浏览器中直接预览的 PlantUML URL，支持官方服务器和自定义服务器。
    同时生成在线编辑器 URL，方便用户在浏览器中编辑和调试 UML 代码。

    Args:
        uml_code (str): PlantUML DSL 代码，完整的 @startuml...@enduml 块
        server_url (str): PlantUML 服务器 URL，默认使用官方服务器
                         支持自定义服务器，如本地部署的 PlantUML 服务
        output_format (str): 输出格式，支持：
                           - png: PNG 图像格式（默认）
                           - svg: SVG 矢量格式
                           - uml: 返回 UML 源码
        use_hex (bool): 编码方式选择：
                       - False: 使用 Deflate 压缩编码（推荐，适用于复杂图表）
                       - True: 使用十六进制编码（适用于简单图表）

    Returns:
        Dict[str, Any]: 预览信息字典，包含：
            - preview_url (str): 可直接访问的预览 URL
            - editor_url (str): PlantUML 在线编辑器 URL
            - encoded_text (str): 编码后的 UML 文本
            - server_url (str): 使用的服务器 URL
            - format (str): 输出格式
            - encoding_method (str): 编码方法（deflate/hex）
            - success (bool): 生成是否成功
            - message (str): 成功消息或错误信息

    Examples:
        >>> # 基本用法 - 生成 PNG 预览
        >>> result = await generate_preview_url(
        ...     uml_code="@startuml\nAlice -> Bob: Hello\n@enduml",
        ...     output_format="png"
        ... )
        >>> print(result["preview_url"])  # 可直接在浏览器中打开
        >>> print(result["editor_url"])   # 可在线编辑的 URL
        >>>
        >>> # 使用 SVG 格式和十六进制编码
        >>> result = await generate_preview_url(
        ...     uml_code="@startuml\nclass User\n@enduml",
        ...     output_format="svg",
        ...     use_hex=True
        ... )
        >>>
        >>> # 使用自定义服务器
        >>> result = await generate_preview_url(
        ...     uml_code="@startuml\nA -> B\n@enduml",
        ...     server_url="http://localhost:8080/plantuml"
        ... )

    Note:
        - 预览 URL 可直接在浏览器中打开查看图表
        - 编辑器 URL 允许用户在线修改和调试 UML 代码
        - Deflate 编码适用于复杂图表，压缩率更高
        - 十六进制编码适用于简单图表，URL 更易读
        - 自定义服务器需要兼容 PlantUML 服务器 API
    """
    try:
        # 验证输入
        validate_uml_input(uml_code, output_format, config)

        # 验证输出格式
        valid_formats = ["png", "svg", "uml", "txt"]
        if output_format not in valid_formats:
            raise ValidationError(
                f"不支持的输出格式: {output_format}，支持的格式: {', '.join(valid_formats)}"
            )

        # 生成预览 URL
        preview_url = PlantUMLEncoder.generate_preview_url(
            plantuml_text=uml_code,
            server_url=server_url,
            output_format=output_format,
            use_hex=use_hex,
        )

        # 获取编码后的文本
        if use_hex:
            encoded_text = PlantUMLEncoder.encode_hex(uml_code)
            encoding_method = "hex"
        else:
            encoded_text = PlantUMLEncoder.encode(uml_code)
            encoding_method = "deflate"

        logger.info(f"生成预览 URL 成功，格式: {output_format}，编码方法: {encoding_method}")

        # 生成在线编辑器URL
        editor_url = f"https://www.plantuml.com/plantuml/uml/{encoded_text}"

        return {
            "preview_url": preview_url,
            "editor_url": editor_url,
            "encoded_text": encoded_text,
            "server_url": server_url,
            "format": output_format,
            "encoding_method": encoding_method,
            "use_hex": use_hex,
            "success": True,
            "message": "预览 URL 和编辑器 URL 生成成功",
        }

    except ValidationError as e:
        logger.warning(f"预览 URL 生成失败 - 输入验证错误: {str(e)}")
        return {
            "preview_url": None,
            "success": False,
            "message": f"输入验证失败: {str(e)}",
            "error_type": "validation_error",
        }
    except Exception as e:
        logger.error(f"预览 URL 生成失败: {str(e)}", exc_info=True)
        return {
            "preview_url": None,
            "success": False,
            "message": f"生成预览 URL 时发生错误: {str(e)}",
            "error_type": "generation_error",
        }


async def startup() -> None:
    """
    服务启动时的初始化操作
    """
    logger.info("正在启动 UML MCP 渲染服务...")

    # 初始化渲染器
    await renderer.initialize()

    # 检查 PlantUML JAR 文件
    if not await renderer.check_plantuml_availability():
        logger.error("PlantUML JAR 文件不可用，请检查配置")
        raise RuntimeError("PlantUML 不可用")

    # 创建临时目录
    os.makedirs(config.temp_dir, exist_ok=True)

    logger.info(f"服务启动成功，监听端口: {config.server_port}")
    logger.info(f"PlantUML JAR 路径: {config.plantuml_jar_path}")
    logger.info(f"最大 UML 大小: {config.max_uml_size} 字节")
    logger.info(f"渲染超时: {config.render_timeout} 秒")


async def shutdown() -> None:
    """
    服务关闭时的清理操作
    """
    logger.info("正在关闭 UML MCP 渲染服务...")

    # 清理临时文件
    await renderer.cleanup()

    logger.info("服务已关闭")


if __name__ == "__main__":
    # 配置统一日志系统
    logging_config = setup_default_logging(
        log_level=config.log_level,
        logs_dir=config.logs_dir
    )

    try:
        # 启动服务器
        asyncio.run(startup())

        # 运行 MCP 服务器 - 使用 STDIO 传输（默认）
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}", exc_info=True)
    finally:
        # 清理资源
        asyncio.run(shutdown())
