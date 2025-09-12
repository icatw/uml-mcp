"""UML渲染器单元测试"""

import asyncio
import os
import tempfile
import unittest
from unittest.mock import Mock, patch, AsyncMock
import base64

import pytest

from src.uml_renderer import UMLRenderer
from src.config import Config
from src.exceptions import (
    UMLRenderError,
    UMLTimeoutError,
    UMLValidationError,
    PlantUMLNotFoundError
)


class TestUMLRenderer(unittest.TestCase):
    """UML渲染器测试类"""
    
    def setUp(self) -> None:
        """测试前置设置"""
        self.config = Config()
        self.renderer = UMLRenderer(self.config)
        
        # 测试用的UML代码
        self.valid_uml = "@startuml\nAlice -> Bob: Hello\n@enduml"
        self.invalid_uml = "invalid uml code"
        self.complex_uml = """
@startuml
class User {
    +username: String
    +email: String
    +login()
    +logout()
}

class Order {
    +id: Long
    +amount: BigDecimal
    +status: OrderStatus
    +create()
    +cancel()
}

class Product {
    +name: String
    +price: BigDecimal
    +description: String
}

User "1" -- "*" Order
Order "*" -- "*" Product
@enduml
"""
    
    def tearDown(self) -> None:
        """测试后清理"""
        # 清理临时文件
        if hasattr(self.renderer, 'temp_dir'):
            import shutil
            try:
                shutil.rmtree(self.renderer.temp_dir, ignore_errors=True)
            except:
                pass
    
    @patch('subprocess.run')
    def test_check_plantuml_availability_success(self, mock_run) -> None:
        """测试PlantUML可用性检查 - 成功"""
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "PlantUML version 1.2024.0"
        
        result = self.renderer.check_plantuml_availability_sync()
        self.assertTrue(result)
    
    @patch('subprocess.run')
    def test_check_plantuml_availability_failure(self, mock_run) -> None:
        """测试PlantUML可用性检查 - 失败"""
        mock_run.side_effect = FileNotFoundError()
        
        with self.assertRaises(PlantUMLNotFoundError):
            self.renderer.check_plantuml_availability_sync()
    
    def test_validate_uml_syntax_valid(self) -> None:
        """测试UML语法验证 - 有效"""
        result = self.renderer.validate_uml_syntax(self.valid_uml)
        self.assertTrue(result)
    
    def test_validate_uml_syntax_invalid(self) -> None:
        """测试UML语法验证 - 无效"""
        with self.assertRaises(UMLValidationError):
            self.renderer.validate_uml_syntax(self.invalid_uml)
    
    def test_validate_uml_syntax_empty(self) -> None:
        """测试UML语法验证 - 空内容"""
        with self.assertRaises(UMLValidationError):
            self.renderer.validate_uml_syntax("")
    
    @patch('subprocess.run')
    async def test_render_uml_success_png(self, mock_run) -> None:
        """测试UML渲染 - PNG格式成功"""
        # 模拟成功的subprocess调用
        mock_run.return_value.returncode = 0
        
        # 创建模拟的PNG文件
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
            # 写入一些测试数据
            test_png_data = b'\x89PNG\r\n\x1a\n' + b'test_image_data'
            temp_file.write(test_png_data)
            temp_file.flush()
            
            # 模拟PlantUML生成文件
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_temp.return_value.__enter__.return_value.name = temp_file.name
                
                result = await self.renderer.render_uml(self.valid_uml, 'png')
                
                self.assertIn('image_base64', result)
                self.assertEqual(result['format'], 'png')
                self.assertIn('metadata', result)
                
                # 验证base64编码
                decoded_data = base64.b64decode(result['image_base64'])
                self.assertEqual(decoded_data, test_png_data)
            
            # 清理临时文件
            os.unlink(temp_file.name)
    
    @patch('subprocess.run')
    async def test_render_uml_success_svg(self, mock_run) -> None:
        """测试UML渲染 - SVG格式成功"""
        mock_run.return_value.returncode = 0
        
        test_svg_data = b'<svg xmlns="http://www.w3.org/2000/svg"><rect width="100" height="100"/></svg>'
        
        with tempfile.NamedTemporaryFile(suffix='.svg', delete=False) as temp_file:
            temp_file.write(test_svg_data)
            temp_file.flush()
            
            with patch('tempfile.NamedTemporaryFile') as mock_temp:
                mock_temp.return_value.__enter__.return_value.name = temp_file.name
                
                result = await self.renderer.render_uml(self.valid_uml, 'svg')
                
                self.assertIn('image_base64', result)
                self.assertEqual(result['format'], 'svg')
                
                decoded_data = base64.b64decode(result['image_base64'])
                self.assertEqual(decoded_data, test_svg_data)
            
            os.unlink(temp_file.name)
    
    @patch('subprocess.run')
    async def test_render_uml_plantuml_error(self, mock_run) -> None:
        """测试UML渲染 - PlantUML执行错误"""
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "PlantUML syntax error"
        
        with self.assertRaises(UMLRenderError):
            await self.renderer.render_uml(self.valid_uml, 'png')
    
    @patch('subprocess.run')
    async def test_render_uml_timeout(self, mock_run) -> None:
        """测试UML渲染 - 超时"""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired('java', 30)
        
        with self.assertRaises(UMLTimeoutError):
            await self.renderer.render_uml(self.valid_uml, 'png')
    
    async def test_render_uml_invalid_format(self) -> None:
        """测试UML渲染 - 无效格式"""
        with self.assertRaises(UMLValidationError):
            await self.renderer.render_uml(self.valid_uml, 'invalid_format')
    
    @patch('src.uml_renderer.UMLRenderer.render_uml')
    async def test_concurrent_rendering(self, mock_render) -> None:
        """测试并发渲染"""
        # 模拟渲染结果
        mock_render.return_value = {
            'image_base64': 'dGVzdA==',
            'format': 'png',
            'metadata': {'size': 100}
        }
        
        # 创建多个并发任务
        tasks = []
        for i in range(5):
            task = asyncio.create_task(
                self.renderer.render_uml(f"{self.valid_uml}_{i}", 'png')
            )
            tasks.append(task)
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks)
        
        # 验证结果
        self.assertEqual(len(results), 5)
        for result in results:
            self.assertIn('image_base64', result)
            self.assertEqual(result['format'], 'png')
    
    def test_get_metrics(self) -> None:
        """测试获取性能指标"""
        metrics = self.renderer.get_metrics()
        
        self.assertIn('total_renders', metrics)
        self.assertIn('successful_renders', metrics)
        self.assertIn('failed_renders', metrics)
        self.assertIn('cache_hits', metrics)
        self.assertIn('cache_misses', metrics)
        self.assertIn('average_render_time', metrics)
    
    async def test_cleanup_resources(self) -> None:
        """测试资源清理"""
        # 执行一些操作创建资源
        await self.renderer.cleanup_resources()
        
        # 验证清理操作（这里主要测试不抛异常）
        self.assertTrue(True)


class TestUMLRendererIntegration(unittest.TestCase):
    """UML渲染器集成测试"""
    
    def setUp(self) -> None:
        """测试前置设置"""
        self.config = Config()
        self.renderer = UMLRenderer(self.config)
    
    @unittest.skipIf(not os.getenv('RUN_INTEGRATION_TESTS'), "跳过集成测试")
    async def test_real_plantuml_rendering(self) -> None:
        """真实PlantUML渲染测试（需要实际环境）"""
        uml_code = "@startuml\nAlice -> Bob: Hello World\n@enduml"
        
        try:
            result = await self.renderer.render_uml(uml_code, 'png')
            
            self.assertIn('image_base64', result)
            self.assertEqual(result['format'], 'png')
            
            # 验证base64数据有效性
            image_data = base64.b64decode(result['image_base64'])
            self.assertTrue(len(image_data) > 0)
            
            # PNG文件应该以特定字节开头
            self.assertTrue(image_data.startswith(b'\x89PNG'))
            
        except PlantUMLNotFoundError:
            self.skipTest("PlantUML未安装，跳过真实渲染测试")


if __name__ == '__main__':
    # 运行测试
    unittest.main()