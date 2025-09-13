"""验证和预览URL相关工具

包含UML语法验证和预览URL生成的工具函数：
- validate_uml_syntax: 验证UML语法
- generate_preview_url: 生成PlantUML预览URL
"""

import re
import zlib
import base64
from typing import Dict, Any, List
from urllib.parse import urljoin

from loguru import logger

from ..config import Config
from ..uml_renderer import UMLRenderer
from ..metrics import RenderMetrics

# 全局变量，将在register_validation_tools中初始化
config: Config = None
renderer: UMLRenderer = None
metrics: RenderMetrics = None


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
        errors = []
        warnings = []
        suggestions = []
        
        # 基本结构检查
        if not uml_code.strip():
            errors.append({
                "line": 1,
                "message": "UML代码不能为空",
                "severity": "error"
            })
            return {
                "valid": False,
                "errors": errors,
                "warnings": warnings,
                "complexity_score": 0.0,
                "estimated_render_time": 0.0,
                "suggestions": ["请提供有效的PlantUML代码"]
            }
        
        lines = uml_code.split('\n')
        
        # 检查开始和结束标记
        has_start = any('@startuml' in line.lower() for line in lines)
        has_end = any('@enduml' in line.lower() for line in lines)
        
        if not has_start:
            errors.append({
                "line": 1,
                "message": "缺少@startuml开始标记",
                "severity": "error"
            })
        
        if not has_end:
            errors.append({
                "line": len(lines),
                "message": "缺少@enduml结束标记",
                "severity": "error"
            })
        
        # 检查代码长度
        if len(uml_code) > config.max_uml_size:
            errors.append({
                "line": 1,
                "message": f"UML代码过长，最大允许{config.max_uml_size}字符",
                "severity": "error"
            })
        
        # 复杂度评估
        complexity_indicators = {
            'participants': len(re.findall(r'participant|actor|boundary|control|entity|database', uml_code, re.IGNORECASE)),
            'arrows': len(re.findall(r'->', uml_code)),
            'notes': len(re.findall(r'note', uml_code, re.IGNORECASE)),
            'loops': len(re.findall(r'loop|alt|opt|par', uml_code, re.IGNORECASE)),
            'classes': len(re.findall(r'class|interface|abstract', uml_code, re.IGNORECASE)),
        }
        
        # 计算复杂度分数 (0-10)
        complexity_score = min(10.0, sum(complexity_indicators.values()) * 0.5)
        
        # 预估渲染时间（基于复杂度）
        estimated_render_time = max(0.1, complexity_score * 0.2)
        
        # 生成建议
        if complexity_score > 7:
            suggestions.append("图表较为复杂，建议分解为多个较小的图表")
        
        if complexity_indicators['participants'] > 10:
            suggestions.append("参与者数量较多，考虑使用分组或简化")
        
        if len(lines) > 100:
            suggestions.append("代码行数较多，建议添加注释和适当的空行")
        
        # 语法警告检查
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if line and not line.startswith('@') and not line.startswith("'") and not line.startswith('/'):
                # 检查常见的语法问题
                if '->' in line and not re.search(r'\w+\s*->\s*\w+', line):
                    warnings.append({
                        "line": i,
                        "message": "箭头语法可能不正确，请检查参与者名称",
                        "severity": "warning"
                    })
        
        is_valid = len(errors) == 0
        
        logger.info(f"UML语法验证完成: valid={is_valid}, errors={len(errors)}, warnings={len(warnings)}")
        
        return {
            "valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "complexity_score": complexity_score,
            "estimated_render_time": estimated_render_time,
            "suggestions": suggestions,
            "line_count": len(lines),
            "character_count": len(uml_code)
        }
        
    except Exception as e:
        logger.error(f"UML语法验证失败: {str(e)}", exc_info=True)
        return {
            "valid": False,
            "errors": [{
                "line": 1,
                "message": f"验证过程中发生错误: {str(e)}",
                "severity": "error"
            }],
            "warnings": [],
            "complexity_score": 0.0,
            "estimated_render_time": 0.0,
            "suggestions": ["请检查UML代码格式"]
        }


async def generate_preview_url(
    uml_code: str,
    server_url: str = "http://www.plantuml.com/plantuml",
    output_format: str = "png",
    use_hex: bool = False
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
        # 验证输入参数
        if not uml_code.strip():
            return {
                "success": False,
                "message": "UML代码不能为空",
                "error_type": "validation_error"
            }
        
        if output_format not in ["png", "svg", "uml"]:
            return {
                "success": False,
                "message": f"不支持的输出格式: {output_format}",
                "error_type": "validation_error"
            }
        
        # 编码UML文本
        if use_hex:
            # 十六进制编码
            encoded_text = uml_code.encode('utf-8').hex()
            encoding_method = "hex"
        else:
            # Deflate压缩编码
            compressed = zlib.compress(uml_code.encode('utf-8'))
            encoded_text = base64.b64encode(compressed).decode('ascii')
            # PlantUML使用特殊的base64字符集
            encoded_text = encoded_text.translate(str.maketrans(
                'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/',
                '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_'
            ))
            encoding_method = "deflate"
        
        # 构建预览URL
        format_path = {
            "png": "png",
            "svg": "svg", 
            "uml": "uml"
        }[output_format]
        
        preview_url = urljoin(server_url.rstrip('/') + '/', f"{format_path}/{encoded_text}")
        
        # 构建编辑器URL（使用官方编辑器）
        editor_url = f"http://www.plantuml.com/plantuml/uml/{encoded_text}"
        
        logger.info(f"生成预览URL成功: format={output_format}, encoding={encoding_method}")
        
        return {
            "success": True,
            "preview_url": preview_url,
            "editor_url": editor_url,
            "encoded_text": encoded_text,
            "server_url": server_url,
            "format": output_format,
            "encoding_method": encoding_method,
            "message": "预览URL生成成功"
        }
        
    except Exception as e:
        logger.error(f"生成预览URL失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"生成预览URL时发生错误: {str(e)}",
            "error_type": "encoding_error"
        }


def register_validation_tools(mcp, config_instance, renderer_instance, metrics_instance):
    """注册验证相关工具到FastMCP实例"""
    global config, renderer, metrics
    
    # 设置全局变量
    config = config_instance
    renderer = renderer_instance
    metrics = metrics_instance
    
    # 注册工具
    mcp.tool(validate_uml_syntax)
    mcp.tool(generate_preview_url)