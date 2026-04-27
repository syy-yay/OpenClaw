FROM m.daocloud.io/docker.io/library/alpine:latest
WORKDIR /app
COPY . .
RUN apk add --no-cache python3 2>/dev/null || true
CMD ["sh", "-c", "python3 -m http.server 8080 2>/dev/null || python -m SimpleHTTPServer 8080"]
