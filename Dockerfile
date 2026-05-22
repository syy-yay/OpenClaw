FROM m.daocloud.io/docker.io/library/alpine:latest
WORKDIR /app

RUN apk add --no-cache python3 py3-pip

RUN adduser -D -H appuser

COPY myproject/ .

RUN pip3 install flask flask-sqlalchemy --break-system-packages 2>/dev/null || \
    pip3 install flask flask-sqlalchemy

RUN mkdir -p /app/instance && \
    chown -R appuser:appuser /app && \
    chmod 755 /app/instance

EXPOSE 5000
USER appuser
CMD ["python3", "app.py"]
