# 📝 UML MCP 渲染服务

基于 **FastMCP** 的 UML 图表渲染服务，支持通过 AI 对话生成各种 UML 图表。

---

## ✨ 核心特性

- 🤖 **MCP 协议支持** - 可作为 AI 工具调用，支持 Claude、Cursor 等客户端
- 📊 **完整 UML 支持** - 支持类图、序列图、组件图等所有 PlantUML 图表类型
- 🎨 **多格式输出** - PNG、SVG 格式，支持 Base64 编码和文件保存
- ⚡ **高性能异步** - 支持并发渲染，内置缓存机制
- 🔒 **安全可靠** - 输入限制、超时控制、完善的错误处理

---

## 🛠️ MCP 工具

提供 **7 个专业的 MCP 工具**，可通过 AI 助手调用：

| 工具                      | 功能   | 说明                              |
|-------------------------|------|---------------------------------|
| `render_uml`            | 核心渲染 | 将 PlantUML 代码渲染为图像，返回 Base64 数据 |
| `render_uml_to_file`    | 文件保存 | 渲染并保存为文件，适合大图表                  |
| `validate_uml_syntax`   | 语法验证 | 快速检查 UML 语法，提供优化建议              |
| `generate_preview_url`  | 在线预览 | 生成可直接访问的预览链接和编辑器 URL            |
| `get_metrics`           | 性能监控 | 获取渲染统计、性能分析、缓存命中率               |
| `get_supported_formats` | 格式查询 | 查看支持的输出格式和详细信息                  |
| `get_service_info`      | 服务信息 | 获取版本信息、配置参数、运行状态                |

---

## 📋 系统要求

- **Python 3.9+**
- **Java 8+** (运行 PlantUML)
- **Graphviz** (可选，渲染复杂图表)
- **uv** 包管理器 (推荐)

### 依赖说明

- 🔄 序列图、时序图、甘特图 —— 无需 Graphviz
- 📦 类图、组件图、状态图、用例图 —— 需要 Graphviz
- 🏗️ 部署图、活动图 —— 需要 Graphviz

### 安装 Graphviz

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz

# Windows
choco install graphviz
````

---

## 🚀 快速开始

### 1. 安装

```bash
# 克隆项目
git clone https://github.com/icatw/uml-mcp
cd uml-mcp

# 安装依赖
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# 下载 PlantUML
curl -L -o plantuml.jar https://github.com/plantuml/plantuml/releases/latest/download/plantuml.jar
```

### 2. 启动服务

```bash
# 直接运行
uv run python server.py

# 或使用启动脚本
./start.sh
```

---

## ⚙️ MCP 客户端配置

### Claude Desktop

编辑配置文件 `~/Library/Application Support/Claude/claude_desktop_config.json`：

```json
{
  "mcpServers": {
    "uml-mcp-renderer": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/uml-mcp",
        "run",
        "python",
        "server.py"
      ],
      "env": {
        "PLANTUML_JAR_PATH": "/path/to/uml-mcp/plantuml.jar",
        "JAVA_EXECUTABLE": "java",
        "RENDER_TIMEOUT": "30",
        "ENABLE_CACHE": "true",
        "OUTPUT_DIR": "/path/to/uml-mcp/output"
      }
    }
  }
}

```

### 其他客户端

* **Cursor IDE**: 在设置中添加 MCP 服务器配置
* **VS Code**: 安装支持 MCP 的 AI 扩展
* **JetBrains**: 在 AI Assistant 设置中配置 MCP 服务器

---

## 📊 支持的图表类型

支持所有 **PlantUML 图表类型**：

* 🔄 序列图
* 📦 类图
* 👤 用例图
* 🔀 活动图
* 🧩 组件图
* 🏗️ 部署图
* 🔄 状态图
* ⏱️ 时序图

---

## 💡 使用示例

### 基本调用

通过 AI 助手直接对话：

```
用户: 请帮我生成一个用户登录的序列图
AI: 我来为你生成用户登录的序列图...
```

AI 会自动调用 **UML MCP 工具**生成图表。

### 示例图表

项目包含完整的示例代码和 8 个 UML 图表：

* 📊 项目架构图
* 🔄 渲染流程图
* 📦 类结构图
* 🎯 用例图
* 🏗️ 部署图

示例见 `examples/` 目录

<p align="center">
  <img src="https://icatw.oss-cn-beijing.aliyuncs.com/images/20250913212151541.png" width="45%">
  <img src="https://icatw.oss-cn-beijing.aliyuncs.com/images/use_case_diagram.svg" width="45%">
</p>

---

## 🐳 Docker 部署

```bash
docker build -t uml-mcp .
docker run -p 8000:8000 uml-mcp
```

---

## 🧪 测试

```bash
# 运行测试
uv run pytest

# 生成覆盖率报告
uv run pytest --cov=src
```

---

## 📈 性能

* ⚡ 渲染速度: < 3 秒
* 🚀 并发支持: 50+ 请求
* 💾 内存占用: < 500MB
* 🔒 安全限制: 输入验证 + 超时控制

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

---

## 📄 许可证

MIT License

---

## 🙏 致谢

* [FastMCP](https://github.com/jlowin/fastmcp)
* [PlantUML](https://plantuml.com/)
* [Model Context Protocol](https://modelcontextprotocol.io/)

---

## 📬 联系我

如果你在使用过程中遇到问题，或者想要交流 MCP 与 UML 渲染相关内容，可以通过以下方式联系我：

* 📧 Email: [762188827@qq.com](mailto:762188827@qq.com)
* 🐙 GitHub: [@icatw](https://github.com/icatw)
* 💬 微信 :

<img src="https://icatw.oss-cn-beijing.aliyuncs.com/images/img_v3_02q4_71be2a38-56c6-4cbd-be1d-9103f786e2bg.jpg" width="30%"/>

欢迎交流与反馈！ 🚀
