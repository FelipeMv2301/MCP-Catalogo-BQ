FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
COPY src/ ./src/
COPY server.py .

RUN pip install --no-cache-dir -e .

ENV MCP_TRANSPORT=sse
ENV PORT=8000

EXPOSE 8000

CMD ["python", "server.py"]
