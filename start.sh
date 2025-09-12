#!/bin/bash

# UML MCP 服务启动脚本
# 用途：简化本地开发和部署流程

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查命令是否存在
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 检查Java环境
check_java() {
    if ! command_exists java; then
        log_error "Java未安装，请先安装Java 8+"
        exit 1
    fi
    
    java_version=$(java -version 2>&1 | head -n1 | cut -d'"' -f2)
    log_info "检测到Java版本: $java_version"
}

# 检查Python环境
check_python() {
    if ! command_exists python3; then
        log_error "Python3未安装，请先安装Python 3.9+"
        exit 1
    fi
    
    python_version=$(python3 --version)
    log_info "检测到Python版本: $python_version"
}

# 检查uv包管理器
check_uv() {
    if ! command_exists uv; then
        log_error "uv包管理器未安装，请先安装uv"
        log_info "安装命令: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    
    uv_version=$(uv --version)
    log_info "检测到uv版本: $uv_version"
}

# 下载PlantUML JAR
download_plantuml() {
    local jar_path="./plantuml.jar"
    
    if [ ! -f "$jar_path" ]; then
        log_info "下载PlantUML JAR文件..."
        
        # 优先使用 curl，如果不存在则尝试 wget
        if command_exists curl; then
            curl -L -o "$jar_path" "https://github.com/plantuml/plantuml/releases/download/v1.2024.0/plantuml-1.2024.0.jar"
        elif command_exists wget; then
            wget -O "$jar_path" "https://github.com/plantuml/plantuml/releases/download/v1.2024.0/plantuml-1.2024.0.jar"
        else
            log_error "未找到 curl 或 wget 命令，请手动下载 PlantUML JAR 文件"
            log_info "下载地址: https://github.com/plantuml/plantuml/releases/download/v1.2024.0/plantuml-1.2024.0.jar"
            log_info "保存为: $jar_path"
            exit 1
        fi
        
        log_success "PlantUML JAR下载完成"
    else
        log_info "PlantUML JAR文件已存在"
    fi
    
    # 测试PlantUML
    if java -jar "$jar_path" -version >/dev/null 2>&1; then
        log_success "PlantUML测试通过"
    else
        log_error "PlantUML测试失败"
        exit 1
    fi
}

# 安装Python依赖
install_dependencies() {
    log_info "安装Python依赖..."
    
    # 优先使用uv，如果存在pyproject.toml
    if [ -f "pyproject.toml" ] && command_exists uv; then
        log_info "使用uv安装依赖..."
        uv sync
        log_success "uv依赖安装完成"
    elif [ -f "requirements.txt" ]; then
        log_info "使用pip安装依赖..."
        python3 -m pip install -r requirements.txt
        log_success "pip依赖安装完成"
    else
        log_error "未找到pyproject.toml或requirements.txt文件"
        exit 1
    fi
}

# 创建必要目录
create_directories() {
    log_info "创建必要目录..."
    mkdir -p temp cache logs
    log_success "目录创建完成"
}

# 设置环境变量
setup_environment() {
    log_info "设置环境变量..."
    
    export PLANTUML_JAR_PATH="$(pwd)/plantuml.jar"
    export UML_TEMP_DIR="$(pwd)/temp"
    export UML_CACHE_DIR="$(pwd)/cache"
    export UML_LOG_LEVEL="INFO"
    export UML_MAX_FILE_SIZE="10485760"
    export UML_TIMEOUT="30"
    export UML_MAX_CONCURRENT="10"
    export PYTHONPATH="$(pwd)"
    
    log_success "环境变量设置完成"
}

# 启动服务
start_server() {
    log_info "启动UML MCP服务..."
    
    # 优先使用uv运行，如果存在pyproject.toml
    if [ -f "pyproject.toml" ] && command_exists uv; then
        log_info "使用uv运行服务..."
        uv run python server.py
    else
        log_info "使用python3运行服务..."
        python3 server.py
    fi
}

# Docker模式启动
start_docker() {
    log_info "使用Docker启动服务..."
    
    if ! command_exists docker; then
        log_error "Docker未安装，请先安装Docker"
        exit 1
    fi
    
    if ! command_exists docker-compose; then
        log_error "Docker Compose未安装，请先安装Docker Compose"
        exit 1
    fi
    
    log_info "构建并启动Docker容器..."
    docker-compose up --build
}

# 显示帮助信息
show_help() {
    echo "UML MCP 服务启动脚本"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  --local     本地模式启动（默认）"
    echo "  --docker    Docker模式启动"
    echo "  --check     仅检查环境依赖"
    echo "  --help      显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0                # 本地模式启动"
    echo "  $0 --docker       # Docker模式启动"
    echo "  $0 --check        # 检查环境"
}

# 主函数
main() {
    local mode="local"
    
    # 解析命令行参数
    while [[ $# -gt 0 ]]; do
        case $1 in
            --local)
                mode="local"
                shift
                ;;
            --docker)
                mode="docker"
                shift
                ;;
            --check)
                mode="check"
                shift
                ;;
            --help)
                show_help
                exit 0
                ;;
            *)
                log_error "未知参数: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    log_info "UML MCP 服务启动脚本"
    log_info "模式: $mode"
    echo ""
    
    case $mode in
        "local")
            check_java
            check_python
            # 如果存在pyproject.toml，则检查uv
            if [ -f "pyproject.toml" ]; then
                check_uv
            fi
            download_plantuml
            install_dependencies
            create_directories
            setup_environment
            start_server
            ;;
        "docker")
            start_docker
            ;;
        "check")
            check_java
            check_python
            log_success "环境检查完成"
            ;;
    esac
}

# 执行主函数
main "$@"