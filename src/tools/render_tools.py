"""UML渲染相关工具

包含UML图表渲染的核心工具函数：
- render_uml: 基础UML渲染工具
- render_uml_to_file: 直接保存到文件的渲染工具
"""

import asyncio
import base64
import os
import time
from typing import Dict, Any, Optional

import aiofiles
from loguru import logger

from ..config import Config
from ..uml_renderer import UMLRenderer
from ..exceptions import UMLRenderError, ValidationError
from ..validators import validate_uml_input
from ..metrics import RenderMetrics

# 全局变量，将在register_render_tools中初始化
config: Config = None
renderer: UMLRenderer = None
metrics: RenderMetrics = None


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


def register_render_tools(mcp, config_instance, renderer_instance, metrics_instance):
    """注册渲染相关工具到FastMCP实例"""
    global config, renderer, metrics
    
    # 设置全局变量
    config = config_instance
    renderer = renderer_instance
    metrics = metrics_instance
    
    # 注册工具
    mcp.tool(render_uml)
    mcp.tool(render_uml_to_file)