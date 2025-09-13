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
import os
from fastmcp import FastMCP
from loguru import logger

from src.config import Config
from src.uml_renderer import UMLRenderer
from src.metrics import RenderMetrics
from src.logging_config import setup_default_logging
from src.tools import register_all_tools

# 初始化配置
config = Config()

# 初始化 FastMCP 服务器
mcp = FastMCP("UML MCP 渲染服务")

# 初始化 UML 渲染器
renderer = UMLRenderer(config)

# 初始化性能指标收集器
metrics = RenderMetrics()

# 注册所有工具
register_all_tools(mcp, config, renderer, metrics)


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
