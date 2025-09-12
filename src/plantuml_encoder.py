#!/usr/bin/env python3
"""
PlantUML URL 编码器

实现 PlantUML 的 URL 编码机制，用于生成可预览的 URL 链接。
基于 PlantUML 官方的编码算法实现。
"""

import base64
import zlib


class PlantUMLEncoder:
    """
    PlantUML URL 编码器

    实现 PlantUML 的文本编码算法，支持生成预览 URL。
    """

    # PlantUML 使用的自定义 Base64 字符集
    PLANTUML_ALPHABET = (
        "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
    )
    STANDARD_ALPHABET = (
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    )

    @classmethod
    def encode(cls, plantuml_text: str) -> str:
        """
        编码 PlantUML 文本为 URL 安全的字符串

        Args:
            plantuml_text (str): PlantUML DSL 代码

        Returns:
            str: 编码后的字符串，可用于构建预览 URL
        """
        # 1. 使用 UTF-8 编码文本
        utf8_bytes = plantuml_text.encode("utf-8")

        # 2. 使用 Deflate 压缩
        compressed = zlib.compress(utf8_bytes, level=9)[2:-4]  # 移除 zlib 头部和尾部

        # 3. 转换为 Base64
        base64_encoded = base64.b64encode(compressed).decode("ascii")

        # 4. 转换为 PlantUML 的自定义字符集
        plantuml_encoded = cls._translate_base64(base64_encoded)

        return plantuml_encoded

    @classmethod
    def decode(cls, encoded_text: str) -> str:
        """
        解码 PlantUML URL 编码的字符串

        Args:
            encoded_text (str): 编码后的字符串

        Returns:
            str: 原始的 PlantUML DSL 代码
        """
        # 1. 从 PlantUML 字符集转换回标准 Base64
        base64_text = cls._translate_from_plantuml(encoded_text)

        # 2. Base64 解码
        compressed = base64.b64decode(base64_text.encode("ascii"))

        # 3. 添加 zlib 头部和尾部，然后解压缩
        zlib_data = b"\x78\x9c" + compressed + b"\x00\x00\x00\x00\x00\x00\x00\x00"
        try:
            decompressed = zlib.decompress(zlib_data)
        except zlib.error:
            # 如果解压缩失败，尝试不同的方法
            decompressed = zlib.decompress(compressed, -15)

        # 4. UTF-8 解码
        return decompressed.decode("utf-8")

    @classmethod
    def _translate_base64(cls, base64_text: str) -> str:
        """
        将标准 Base64 字符集转换为 PlantUML 字符集
        """
        translation_table = str.maketrans(cls.STANDARD_ALPHABET, cls.PLANTUML_ALPHABET)
        return base64_text.translate(translation_table)

    @classmethod
    def _translate_from_plantuml(cls, plantuml_text: str) -> str:
        """
        将 PlantUML 字符集转换回标准 Base64 字符集
        """
        translation_table = str.maketrans(cls.PLANTUML_ALPHABET, cls.STANDARD_ALPHABET)
        return plantuml_text.translate(translation_table)

    @classmethod
    def encode_hex(cls, plantuml_text: str) -> str:
        """
        使用十六进制编码（适用于简单场景，无压缩）

        Args:
            plantuml_text (str): PlantUML DSL 代码

        Returns:
            str: 十六进制编码的字符串，需要在前面加上 ~h 前缀
        """
        utf8_bytes = plantuml_text.encode("utf-8")
        hex_encoded = utf8_bytes.hex().upper()
        return f"~h{hex_encoded}"

    @classmethod
    def generate_preview_url(
        cls,
        plantuml_text: str,
        server_url: str = "http://www.plantuml.com/plantuml",
        output_format: str = "png",
        use_hex: bool = False,
    ) -> str:
        """
        生成 PlantUML 预览 URL

        Args:
            plantuml_text (str): PlantUML DSL 代码
            server_url (str): PlantUML 服务器 URL
            output_format (str): 输出格式 (png, svg, uml)
            use_hex (bool): 是否使用十六进制编码

        Returns:
            str: 完整的预览 URL
        """
        if use_hex:
            encoded = cls.encode_hex(plantuml_text)
        else:
            encoded = cls.encode(plantuml_text)

        # 移除服务器 URL 末尾的斜杠
        server_url = server_url.rstrip("/")

        return f"{server_url}/{output_format}/{encoded}"

    @classmethod
    def generate_local_preview_url(
        cls,
        plantuml_text: str,
        base_url: str = "http://localhost:8080",
        output_format: str = "png",
    ) -> str:
        """
        生成本地预览 URL（如果有本地 PlantUML 服务器）

        Args:
            plantuml_text (str): PlantUML DSL 代码
            base_url (str): 本地服务器 URL
            output_format (str): 输出格式

        Returns:
            str: 本地预览 URL
        """
        return cls.generate_preview_url(
            plantuml_text, server_url=base_url, output_format=output_format
        )

    @classmethod
    def generate_editor_url(cls, plantuml_text: str, use_hex: bool = False) -> str:
        """
        生成PlantUML在线编辑器URL

        Args:
            plantuml_text (str): PlantUML DSL代码
            use_hex (bool): 是否使用十六进制编码

        Returns:
            str: 在线编辑器URL
        """
        if use_hex:
            encoded_text = cls.encode_hex(plantuml_text)
        else:
            encoded_text = cls.encode(plantuml_text)

        return f"https://www.plantuml.com/plantuml/uml/{encoded_text}"
