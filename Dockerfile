FROM m.daocloud.io/docker.io/library/alpine:latest
WORKDIR /app

# 安装 Python 和依赖
RUN apk add --no-cache python3 py3-pip

# 复制项目文件
COPY myproject/ .

# 安装 Flask 依赖
RUN pip3 install flask flask-sqlalchemy --break-system-packages 2>/dev/null || \
    pip3 install flask flask-sqlalchemy

# 创建非特权用户并设置 instance 目录权限
RUN adduser -D -H appuser && \
    mkdir -p /app/instance && \
    chown -R appuser:appuser /app && \
    chmod 755 /app/instance

# 暴露端口
EXPOSE 5000

# 切换到非特权用户
USER appuser

CMD ["python3", "app.py"]
