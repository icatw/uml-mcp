#!/usr/bin/env python3
"""
输入验证模块

提供 UML MCP 渲染服务的输入参数验证功能。
包括 UML 语法验证、格式验证、复杂度检查和安全性验证。

Author: UML MCP Team
Version: 1.0.0
"""

import re
from typing import List, Dict, Any

from .exceptions import (
    ValidationError,
    FileSizeExceededError,
    UnsupportedFormatError,
    InvalidUMLSyntaxError,
)
from .config import Config


def validate_uml_input(uml_code: str, format: str, config: Config) -> None:
    """
    验证 UML 输入参数

    对输入的 UML 代码进行全面验证，包括基本格式、大小限制、
    语法结构和复杂度检查。这是渲染前的主要验证入口。

    Args:
        uml_code (str): UML DSL 代码，必须是有效的 PlantUML 语法
        format (str): 输出格式（png, svg 等）
        config (Config): 配置对象，包含验证规则和限制

    Raises:
        ValidationError: 基本验证失败（如空代码）
        FileSizeExceededError: UML 代码大小超过配置限制
        UnsupportedFormatError: 请求的输出格式不被支持
        InvalidUMLSyntaxError: UML 语法结构错误

    Examples:
        >>> config = Config()
        >>> uml_code = "@startuml\nAlice -> Bob: Hello\n@enduml"
        >>> validate_uml_input(uml_code, "png", config)  # 验证通过
        >>> validate_uml_input("", "png", config)  # 抛出 ValidationError

    Note:
        此函数会依次调用多个子验证函数，任何一个验证失败都会抛出相应异常。
    """
    # 验证 UML 代码不为空
    if not uml_code or not uml_code.strip():
        raise ValidationError("UML 代码不能为空", field="uml_code")

    # 验证文件大小
    uml_size = len(uml_code.encode("utf-8"))
    if uml_size > config.max_uml_size:
        raise FileSizeExceededError(
            f"UML 代码大小 ({uml_size} 字节) 超过限制 ({config.max_uml_size} 字节)",
            size=uml_size,
            max_size=config.max_uml_size,
        )

    # 验证输出格式
    if format not in config.allowed_formats:
        raise UnsupportedFormatError(
            f"不支持的输出格式: {format}",
            format=format,
            supported_formats=config.allowed_formats,
        )

    # 验证 UML 基本语法结构
    validate_uml_syntax(uml_code)

    # 验证 UML 复杂度
    validate_uml_complexity(uml_code, config.max_diagram_complexity)


def validate_uml_syntax(uml_code: str) -> None:
    """
    验证 UML 语法结构

    检查 UML 代码的基本语法结构，确保包含正确的开始和结束标记，
    以及标记的正确配对。这是 PlantUML 渲染的基本要求。

    Args:
        uml_code (str): UML DSL 代码，应包含完整的 UML 块

    Raises:
        InvalidUMLSyntaxError: 当 UML 语法结构不正确时抛出，包括：
            - 缺少 @startuml 开始标记
            - 缺少 @enduml 结束标记
            - 开始和结束标记数量不匹配
            - 没有找到任何 UML 块

    Examples:
        >>> validate_uml_syntax("@startuml\nA -> B\n@enduml")  # 验证通过
        >>> validate_uml_syntax("A -> B")  # 抛出 InvalidUMLSyntaxError
        >>> validate_uml_syntax("@startuml\nA -> B")  # 抛出 InvalidUMLSyntaxError

    Note:
        此函数只检查基本的语法结构，不验证 PlantUML 的具体语法正确性。
    """
    # 检查是否包含 @startuml 和 @enduml
    if not uml_code.strip().startswith("@startuml"):
        raise InvalidUMLSyntaxError(
            "UML 代码必须以 @startuml 开始", syntax_error="Missing @startuml"
        )

    if not uml_code.strip().endswith("@enduml"):
        raise InvalidUMLSyntaxError(
            "UML 代码必须以 @enduml 结束", syntax_error="Missing @enduml"
        )

    # 检查 @startuml 和 @enduml 的配对
    start_count = uml_code.count("@startuml")
    end_count = uml_code.count("@enduml")

    if start_count != end_count:
        raise InvalidUMLSyntaxError(
            f"@startuml ({start_count}) 和 @enduml ({end_count}) 数量不匹配",
            syntax_error="Mismatched start/end tags",
        )

    if start_count == 0:
        raise InvalidUMLSyntaxError(
            "UML 代码必须包含至少一个 @startuml/@enduml 对", syntax_error="No UML blocks found"
        )

    # 检查嵌套的 @startuml/@enduml（不允许）
    lines = uml_code.split("\n")
    uml_stack: List[str] = []

    for line_num, line in enumerate(lines, 1):
        line = line.strip()

        if line.startswith("@startuml"):
            if uml_stack:  # 已经在一个 UML 块内
                raise InvalidUMLSyntaxError(
                    f"第 {line_num} 行: 不允许嵌套的 @startuml",
                    line_number=line_num,
                    syntax_error="Nested @startuml not allowed",
                )
            uml_stack.append(str(line_num))

        elif line.startswith("@enduml"):
            if not uml_stack:
                raise InvalidUMLSyntaxError(
                    f"第 {line_num} 行: @enduml 没有对应的 @startuml",
                    line_number=line_num,
                    syntax_error="@enduml without @startuml",
                )
            uml_stack.pop()

    # 检查是否有未关闭的 @startuml
    if uml_stack:
        raise InvalidUMLSyntaxError(
            f"第 {uml_stack[0]} 行的 @startuml 没有对应的 @enduml",
            line_number=int(uml_stack[0]),
            syntax_error="Unclosed @startuml",
        )


def _get_complexity_patterns() -> Dict[str, int]:
    """
    获取UML复杂度计算模式

    Returns:
        Dict[str, int]: 正则表达式模式到复杂度分数的映射
    """
    return {
        # 类和接口
        r"\bclass\s+\w+": 5,
        r"\binterface\s+\w+": 5,
        r"\babstract\s+class\s+\w+": 6,
        r"\benum\s+\w+": 4,
        # 关系
        r"-->": 2,
        r"->": 2,
        r"<--": 2,
        r"<-": 2,
        r"\|>": 3,
        r"<\|": 3,
        r"\*--": 3,
        r"--\*": 3,
        r"o--": 3,
        r"--o": 3,
        # 序列图元素
        r"\bparticipant\s+\w+": 3,
        r"\bactor\s+\w+": 3,
        r"\bactivate\s+\w+": 2,
        r"\bdeactivate\s+\w+": 2,
        r"\balt\b": 4,
        r"\belse\b": 2,
        r"\bopt\b": 3,
        r"\bloop\b": 4,
        r"\bpar\b": 4,
        r"\bnote\s+": 2,
        # 用例图元素
        r"\busecase\s+": 3,
        r"\bactor\s+": 3,
        # 活动图元素
        r"\bstart\b": 2,
        r"\bstop\b": 2,
        r"\bend\b": 2,
        r"\bif\s*\(": 4,
        r"\bwhile\s*\(": 4,
        r"\brepeat\b": 4,
        # 状态图元素
        r"\bstate\s+\w+": 3,
        r"\[\*\]": 2,
        # 组件图元素
        r"\bcomponent\s+": 4,
        r"\bpackage\s+": 3,
        r"\bnode\s+": 4,
        # 部署图元素
        r"\bartifact\s+": 3,
        r"\bdatabase\s+": 4,
        # 通用元素
        r"\bnote_general\s+": 1,
        r"\btitle\s+": 1,
        r"\blegend\b": 2,
        r"\bfooter\s+": 1,
        r"\bheader\s+": 1,
    }


def _calculate_pattern_complexity(uml_code: str) -> float:
    """
    计算基于模式匹配的复杂度分数

    Args:
        uml_code (str): UML代码

    Returns:
        float: 模式匹配的复杂度分数
    """
    complexity_score = 0.0
    complexity_patterns = _get_complexity_patterns()

    for pattern, score in complexity_patterns.items():
        matches = re.findall(pattern, uml_code, re.IGNORECASE | re.MULTILINE)
        complexity_score += len(matches) * score

    return complexity_score


def _calculate_line_complexity(uml_code: str) -> float:
    """
    计算基于代码行数的复杂度分数

    Args:
        uml_code (str): UML代码

    Returns:
        float: 行数复杂度分数
    """
    lines = uml_code.split("\n")
    non_empty_lines = [
        line for line in lines
        if line.strip() and not line.strip().startswith("/")
    ]
    return len(non_empty_lines) * 0.5


def validate_uml_complexity(uml_code: str, max_complexity: int) -> None:
    """
    验证 UML 图表复杂度

    通过统计关键元素数量来估算复杂度，防止过于复杂的图表导致渲染超时。
    复杂度计算基于不同 UML 元素的权重，包括类、关系、控制结构等。

    Args:
        uml_code (str): UML DSL 代码，包含完整的 PlantUML 语法
        max_complexity (int): 最大允许复杂度分数

    Raises:
        ValidationError: 当计算出的复杂度分数超过限制时抛出

    Examples:
        >>> simple_uml = "@startuml\nA -> B\n@enduml"
        >>> validate_uml_complexity(simple_uml, 100)  # 验证通过
        >>> complex_uml = (
        ...     "@startuml\n" + "\n".join([f"class C{i}" for i in range(50)])
        ...     + "\n@enduml"
        ... )
        >>> validate_uml_complexity(complex_uml, 10)  # 抛出 ValidationError

    Note:
        复杂度计算规则：
        - 类/接口：5-6分
        - 关系箭头：2-3分
        - 控制结构：3-4分
        - 每行代码：0.5分
    """
    # 计算总复杂度分数
    pattern_complexity = _calculate_pattern_complexity(uml_code)
    line_complexity = _calculate_line_complexity(uml_code)
    total_complexity = pattern_complexity + line_complexity

    # 检查复杂度限制
    if total_complexity > max_complexity:
        raise ValidationError(
            f"UML 图表复杂度 ({total_complexity:.1f}) 超过限制 ({max_complexity})",
            field="uml_complexity",
            value=str(total_complexity),
        )


def validate_format(format: str, allowed_formats: List[str]) -> None:
    """
    验证输出格式

    检查请求的输出格式是否在支持的格式列表中。

    Args:
        format (str): 请求的输出格式（如 'png', 'svg'）
        allowed_formats (List[str]): 系统支持的格式列表

    Raises:
        UnsupportedFormatError: 当请求的格式不在支持列表中时抛出

    Examples:
        >>> validate_format("png", ["png", "svg"])  # 验证通过
        >>> validate_format("pdf", ["png", "svg"])  # 抛出 UnsupportedFormatError
    """
    if format not in allowed_formats:
        raise UnsupportedFormatError(
            f"不支持的输出格式: {format}", format=format, supported_formats=allowed_formats
        )


def sanitize_uml_code(uml_code: str) -> str:
    """
    清理和标准化 UML 代码

    移除多余的空白字符，标准化行尾，清理开头和结尾的空行。
    这有助于提高缓存效率和减少渲染错误。

    Args:
        uml_code (str): 原始 UML 代码，可能包含多余的空白字符

    Returns:
        str: 清理后的 UML 代码，格式标准化

    Examples:
        >>> messy_code = "  @startuml  \n\n  A -> B  \n\n  @enduml  \n\n"
        >>> clean_code = sanitize_uml_code(messy_code)
        >>> print(repr(clean_code))  # '@startuml\n\n  A -> B\n\n  @enduml'

    Note:
        - 保留图表中的空行，因为它们可能在某些 PlantUML 语法中有意义
        - 只移除开头和结尾的完全空白行
        - 移除每行的尾部空白字符
    """
    # 移除多余的空白字符
    lines = uml_code.split("\n")
    cleaned_lines = []

    for line in lines:
        # 移除行尾空白
        line = line.rstrip()

        # 保留空行（可能在某些图表中有意义）
        cleaned_lines.append(line)

    # 移除开头和结尾的空行
    while cleaned_lines and not cleaned_lines[0].strip():
        cleaned_lines.pop(0)

    while cleaned_lines and not cleaned_lines[-1].strip():
        cleaned_lines.pop()

    return "\n".join(cleaned_lines)


def _get_basic_metadata(uml_code: str) -> Dict[str, Any]:
    """
    获取UML代码的基本统计信息

    Args:
        uml_code (str): UML代码

    Returns:
        Dict[str, Any]: 基本统计信息
    """
    return {
        "line_count": len(uml_code.split("\n")),
        "character_count": len(uml_code),
        "byte_size": len(uml_code.encode("utf-8")),
    }


def _detect_diagram_type(uml_code: str) -> str:
    """
    检测UML图表类型

    Args:
        uml_code (str): UML代码

    Returns:
        str: 检测到的图表类型
    """
    uml_lower = uml_code.lower()

    if "participant" in uml_lower or ("actor" in uml_lower and "->" in uml_code):
        return "sequence"
    elif "class" in uml_lower and (
        "extends" in uml_lower or "implements" in uml_lower or "--|>" in uml_code
    ):
        return "class"
    elif "usecase" in uml_lower or ("actor" in uml_lower and "usecase" in uml_lower):
        return "usecase"
    elif "start" in uml_lower and "stop" in uml_lower:
        return "activity"
    elif "state" in uml_lower and "[*]" in uml_code:
        return "state"
    elif "component" in uml_lower or "package" in uml_lower:
        return "component"
    elif "node" in uml_lower or "artifact" in uml_lower:
        return "deployment"

    return "unknown"


def _check_diagram_features(uml_code: str) -> Dict[str, bool]:
    """
    检查UML图表的特性

    Args:
        uml_code (str): UML代码

    Returns:
        Dict[str, bool]: 特性检查结果
    """
    uml_lower = uml_code.lower()
    return {
        "has_title": "title" in uml_lower,
        "has_legend": "legend" in uml_lower,
    }


def _calculate_complexity_indicators(uml_code: str) -> Dict[str, int]:
    """
    计算复杂度指标

    Args:
        uml_code (str): UML代码

    Returns:
        Dict[str, int]: 复杂度指标
    """
    return {
        "arrow_count": (
            uml_code.count("->")
            + uml_code.count("<-")
            + uml_code.count("-->")
            + uml_code.count("<--")
        ),
        "class_count": len(re.findall(r"\bclass\s+\w+", uml_code, re.IGNORECASE)),
        "participant_count": len(
            re.findall(r"\bparticipant\s+\w+", uml_code, re.IGNORECASE)
        ),
        "note_count": len(re.findall(r"\bnote\s+", uml_code, re.IGNORECASE)),
    }


def extract_uml_metadata(uml_code: str) -> Dict[str, Any]:
    """
    提取 UML 代码的元数据信息

    分析 UML 代码并提取有用的元数据，包括基本统计信息、
    图表类型检测和复杂度指标。用于监控、缓存和优化决策。

    Args:
        uml_code (str): UML DSL 代码，应为有效的 PlantUML 语法

    Returns:
        Dict[str, Any]: 包含以下字段的元数据字典：
            - line_count (int): 代码行数
            - character_count (int): 字符总数
            - byte_size (int): UTF-8 编码后的字节大小
            - diagram_type (str): 检测到的图表类型
            - has_title (bool): 是否包含标题
            - has_legend (bool): 是否包含图例
            - complexity_indicators (Dict): 复杂度相关指标

    Examples:
        >>> uml_code = "@startuml\ntitle My Diagram\nA -> B\n@enduml"
        >>> metadata = extract_uml_metadata(uml_code)
        >>> print(metadata["diagram_type"])  # "sequence"
        >>> print(metadata["has_title"])     # True
        >>> print(metadata["line_count"])    # 4

    Note:
        图表类型检测基于关键字匹配，可能不是100%准确。
        复杂度指标可用于性能优化和资源分配决策。
    """
    # 获取基本统计信息
    metadata = _get_basic_metadata(uml_code)

    # 检测图表类型
    metadata["diagram_type"] = _detect_diagram_type(uml_code)

    # 检查图表特性
    features = _check_diagram_features(uml_code)
    metadata.update(features)

    # 计算复杂度指标
    metadata["complexity_indicators"] = _calculate_complexity_indicators(uml_code)

    return metadata
