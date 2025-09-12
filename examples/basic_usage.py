#!/usr/bin/env python3
"""UML MCP 服务基本使用示例"""

import asyncio
import json
import base64
from pathlib import Path

# 导入MCP相关模块
try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("请先安装MCP客户端: pip install mcp")
    exit(1)


class UMLMCPClient:
    """UML MCP客户端示例"""
    
    def __init__(self, server_path: str = "python server.py") -> None:
        self.server_path = server_path
        self.session = None
    
    async def __aenter__(self) -> 'UMLMCPClient':
        """异步上下文管理器入口"""
        server_params = StdioServerParameters(
            command="python3 server.py",
            env=None
        )
        
        self.session = await stdio_client(server_params).__aenter__()
        await self.session.initialize()
        
        print("✅ 已连接到UML MCP服务器")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        if self.session:
            await self.session.__aexit__(exc_type, exc_val, exc_tb)
            print("✅ 已断开MCP服务器连接")
    
    async def render_uml(self, uml_code: str, format: str = "png") -> dict:
        """渲染UML图"""
        if not self.session:
            raise RuntimeError("未连接到MCP服务器")
        
        try:
            result = await self.session.call_tool(
                "render_uml",
                {
                    "uml_code": uml_code,
                    "format": format
                }
            )
            
            # 解析返回结果
            if result.content and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, 'text'):
                    return json.loads(content.text)
                else:
                    return {"success": False, "error": "无效的返回格式"}
            else:
                return {"success": False, "error": "无返回内容"}
                
        except Exception as e:
            print(f"❌ 渲染失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def save_image(self, result: dict, filename: str) -> str:
        """保存渲染结果到文件"""
        if not result.get('success', False):
            raise ValueError(f"渲染失败: {result.get('error', '未知错误')}")
            
        if 'data' not in result:
            raise ValueError("结果中没有图像数据")
        
        image_data = base64.b64decode(result['data'])
        
        output_path = Path(filename)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'wb') as f:
            f.write(image_data)
        
        print(f"✅ 图像已保存到: {output_path}")
        return output_path


async def example_class_diagram():
    """示例1: 类图"""
    print("\n=== 示例1: 类图 ===")
    
    uml_code = """
@startuml
title 电商系统类图

class User {
    -id: Long
    -username: String
    -email: String
    -password: String
    +login(username, password): boolean
    +logout(): void
    +updateProfile(info): void
}

class Order {
    -id: Long
    -userId: Long
    -totalAmount: BigDecimal
    -status: OrderStatus
    -createTime: DateTime
    +create(): void
    +cancel(): void
    +pay(): void
}

class Product {
    -id: Long
    -name: String
    -price: BigDecimal
    -description: String
    -stock: Integer
    +updateStock(quantity): void
    +getInfo(): ProductInfo
}

class OrderItem {
    -orderId: Long
    -productId: Long
    -quantity: Integer
    -price: BigDecimal
}

enum OrderStatus {
    PENDING
    PAID
    SHIPPED
    DELIVERED
    CANCELLED
}

User ||--o{ Order : places
Order ||--o{ OrderItem : contains
Product ||--o{ OrderItem : "ordered as"
Order }o--|| OrderStatus : has

@enduml
"""
    
    async with UMLMCPClient() as client:
        result = await client.render_uml(uml_code, "png")
        await client.save_image(result, "output/class_diagram.png")
        
        print(f"📊 类图渲染完成")
        print(f"📏 图像大小: {result.get('metadata', {}).get('size', 'unknown')} bytes")


async def example_sequence_diagram():
    """示例2: 时序图"""
    print("\n=== 示例2: 时序图 ===")
    
    uml_code = """
@startuml
title 用户登录时序图

actor User as U
participant "Web Browser" as B
participant "API Gateway" as G
participant "Auth Service" as A
participant "User Database" as D

U -> B: 输入用户名密码
activate B

B -> G: POST /api/login
activate G

G -> A: 验证用户凭据
activate A

A -> D: 查询用户信息
activate D
D --> A: 返回用户数据
deactivate D

alt 验证成功
    A --> G: 返回JWT Token
    G --> B: 200 OK + Token
    B --> U: 登录成功，跳转首页
else 验证失败
    A --> G: 返回错误信息
    G --> B: 401 Unauthorized
    B --> U: 显示错误提示
end

deactivate A
deactivate G
deactivate B

@enduml
"""
    
    async with UMLMCPClient() as client:
        result = await client.render_uml(uml_code, "svg")
        await client.save_image(result, "output/sequence_diagram.svg")
        
        print(f"📊 时序图渲染完成")


async def example_use_case_diagram():
    """示例3: 用例图"""
    print("\n=== 示例3: 用例图 ===")
    
    uml_code = """
@startuml
title 电商系统用例图

left to right direction

actor Customer as C
actor Admin as A
actor "Payment System" as P

rectangle "电商系统" {
    usecase "浏览商品" as UC1
    usecase "搜索商品" as UC2
    usecase "添加到购物车" as UC3
    usecase "下单" as UC4
    usecase "支付" as UC5
    usecase "查看订单" as UC6
    usecase "管理商品" as UC7
    usecase "管理订单" as UC8
    usecase "查看统计" as UC9
}

C --> UC1
C --> UC2
C --> UC3
C --> UC4
C --> UC5
C --> UC6

A --> UC7
A --> UC8
A --> UC9

UC5 --> P : <<include>>

UC4 ..> UC3 : <<extend>>
UC5 ..> UC4 : <<extend>>

@enduml
"""
    
    async with UMLMCPClient() as client:
        result = await client.render_uml(uml_code, "png")
        await client.save_image(result, "output/usecase_diagram.png")
        
        print(f"📊 用例图渲染完成")


async def example_component_diagram():
    """示例4: 组件图"""
    print("\n=== 示例4: 组件图 ===")
    
    uml_code = """
@startuml
title 微服务架构组件图

!define RECTANGLE class

package "前端层" {
    [Web App] as WEB
    [Mobile App] as MOBILE
}

package "API网关层" {
    [API Gateway] as GATEWAY
}

package "业务服务层" {
    [用户服务] as USER_SVC
    [商品服务] as PRODUCT_SVC
    [订单服务] as ORDER_SVC
    [支付服务] as PAYMENT_SVC
}

package "数据层" {
    database "用户数据库" as USER_DB
    database "商品数据库" as PRODUCT_DB
    database "订单数据库" as ORDER_DB
    queue "消息队列" as MQ
}

package "外部服务" {
    [第三方支付] as PAY_GATEWAY
    [短信服务] as SMS
}

WEB --> GATEWAY : HTTPS
MOBILE --> GATEWAY : HTTPS

GATEWAY --> USER_SVC : gRPC
GATEWAY --> PRODUCT_SVC : gRPC
GATEWAY --> ORDER_SVC : gRPC
GATEWAY --> PAYMENT_SVC : gRPC

USER_SVC --> USER_DB : SQL
PRODUCT_SVC --> PRODUCT_DB : SQL
ORDER_SVC --> ORDER_DB : SQL

ORDER_SVC --> MQ : 发布订单事件
PAYMENT_SVC --> MQ : 订阅订单事件
PAYMENT_SVC --> PAY_GATEWAY : API
USER_SVC --> SMS : API

@enduml
"""
    
    async with UMLMCPClient() as client:
        result = await client.render_uml(uml_code, "svg")
        await client.save_image(result, "output/component_diagram.svg")
        
        print(f"📊 组件图渲染完成")


async def example_batch_rendering():
    """示例5: 批量渲染"""
    print("\n=== 示例5: 批量渲染 ===")
    
    diagrams = [
        {
            "name": "simple_class",
            "code": "@startuml\nclass A\nclass B\nA --> B\n@enduml",
            "format": "png"
        },
        {
            "name": "simple_sequence",
            "code": "@startuml\nAlice -> Bob: Hello\nBob -> Alice: Hi\n@enduml",
            "format": "svg"
        },
        {
            "name": "simple_activity",
            "code": "@startuml\nstart\n:Action 1;\n:Action 2;\nstop\n@enduml",
            "format": "png"
        }
    ]
    
    async with UMLMCPClient() as client:
        for diagram in diagrams:
            print(f"🔄 渲染 {diagram['name']}...")
            result = await client.render_uml(diagram['code'], diagram['format'])
            filename = f"output/batch_{diagram['name']}.{diagram['format']}"
            await client.save_image(result, filename)
            print(f"✅ {diagram['name']} 完成")
        
        print(f"📊 批量渲染完成，共处理 {len(diagrams)} 个图表")


async def main() -> None:
    """主函数"""
    print("🚀 UML MCP 服务使用示例")
    print("=" * 50)
    
    # 创建输出目录
    Path("output").mkdir(exist_ok=True)
    
    try:
        # 运行所有示例
        await example_class_diagram()
        await example_sequence_diagram()
        await example_use_case_diagram()
        await example_component_diagram()
        await example_batch_rendering()
        
        print("\n🎉 所有示例执行完成！")
        print("📁 输出文件保存在 output/ 目录中")
        
    except Exception as e:
        print(f"❌ 执行失败: {e}")
        raise


if __name__ == "__main__":
    # 运行示例
    asyncio.run(main())