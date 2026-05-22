FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN adduser --disabled-password --gecos '' appuser

COPY . .

# 合并成一条 RUN，确保在同一层完成
RUN mkdir -p /app/instance && chown -R appuser:appuser /app && chmod 755 /app/instance

EXPOSE 5000
USER appuser
CMD ["python", "app.py"]
