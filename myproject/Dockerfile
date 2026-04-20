FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装Python依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非特权用户
RUN adduser --disabled-password --gecos '' appuser

# 暴露端口
EXPOSE 5000

# 设置工作目录
WORKDIR /app

# 切换到非特权用户
USER appuser

# 启动应用
CMD ["python", "app.py"]