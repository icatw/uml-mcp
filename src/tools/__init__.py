"""工具模块

包含所有UML渲染相关的工具函数，按功能分类组织：
- render_tools: UML渲染相关工具
- service_tools: 服务信息和指标工具
- validation_tools: 验证和预览URL工具
"""

from .render_tools import register_render_tools
from .service_tools import register_service_tools
from .validation_tools import register_validation_tools


def register_all_tools(mcp, config, renderer, metrics):
    """注册所有工具到FastMCP实例
    
    Args:
        mcp: FastMCP实例
        config: 配置实例
        renderer: UML渲染器实例
        metrics: 指标收集器实例
    """
    # 传递依赖组件给各个工具模块
    register_render_tools(mcp, config, renderer, metrics)
    register_service_tools(mcp, config, renderer, metrics)
    register_validation_tools(mcp, config, renderer, metrics)