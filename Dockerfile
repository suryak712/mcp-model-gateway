FROM python:3.12-slim

WORKDIR /app
RUN useradd --create-home --uid 10001 gateway

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

COPY models.yaml ./
# The public key is mounted at run time; the image never contains keys or secrets.
ENV GATEWAY_PUBLIC_KEY=/keys/public.pem \
    GATEWAY_REGISTRY=/app/models.yaml \
    GATEWAY_AUDIT_LOG=/tmp/audit.log.jsonl \
    GATEWAY_BACKEND_URL=http://host.docker.internal:11434/v1

USER gateway
EXPOSE 8000
CMD ["python", "-c", "import uvicorn; from gateway.config import Settings; from gateway.server import build_server, build_service; s = Settings.from_env(); uvicorn.run(build_server(s, build_service(s)).streamable_http_app(host='0.0.0.0'), host='0.0.0.0', port=8000)"]
