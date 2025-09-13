"""服务信息和指标相关工具

包含服务状态、性能指标和配置信息的工具函数：
- get_metrics: 获取服务性能指标
- get_supported_formats: 获取支持的输出格式
- get_service_info: 获取服务信息和配置
"""

import time
from typing import Dict, Any

from loguru import logger

from ..config import Config
from ..uml_renderer import UMLRenderer
from ..metrics import RenderMetrics

# 全局变量，将在register_service_tools中初始化
config: Config = None
renderer: UMLRenderer = None
metrics: RenderMetrics = None


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


def register_service_tools(mcp, config_instance, renderer_instance, metrics_instance):
    """注册服务相关工具到FastMCP实例"""
    global config, renderer, metrics
    
    # 设置全局变量
    config = config_instance
    renderer = renderer_instance
    metrics = metrics_instance
    
    # 注册工具
    mcp.tool(get_metrics)
    mcp.tool(get_supported_formats)
    mcp.tool(get_service_info)