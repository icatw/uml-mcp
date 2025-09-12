FROM python:3.11-slim

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    openjdk-17-jre-headless \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 下载PlantUML JAR文件
RUN wget -O /app/plantuml.jar https://github.com/plantuml/plantuml/releases/download/v1.2024.0/plantuml-1.2024.0.jar

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/temp /app/cache /app/logs

# 设置环境变量
ENV PLANTUML_JAR_PATH=/app/plantuml.jar
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH="$JAVA_HOME/bin:$PATH"
ENV PYTHONPATH=/app
ENV UML_TEMP_DIR=/app/temp
ENV UML_CACHE_DIR=/app/cache
ENV UML_LOG_LEVEL=INFO
ENV UML_MAX_FILE_SIZE=10485760
ENV UML_TIMEOUT=30
ENV UML_MAX_CONCURRENT=10

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import subprocess; subprocess.run(['java', '-jar', '/app/plantuml.jar', '-version'], check=True)"

# 暴露端口（如果需要HTTP服务）
EXPOSE 8000

# 设置用户权限
RUN useradd -m -u 1000 umluser && \
    chown -R umluser:umluser /app
USER umluser

# 启动命令
CMD ["python", "server.py"]