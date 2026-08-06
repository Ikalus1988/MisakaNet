FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml README.md ./
COPY search_knowledge.py ./
COPY misakanet/ ./misakanet/
COPY scripts/mcp_server.py scripts/mcp_server.py
COPY scripts/misaka_run.py scripts/misaka_run.py
COPY scripts/misaka_capture.py scripts/misaka_capture.py
COPY scripts/usage_meter.py scripts/usage_meter.py
COPY scripts/contribution_queue.py scripts/contribution_queue.py
COPY scripts/contribution_review.py scripts/contribution_review.py
COPY lessons/ ./lessons/
COPY data/ ./data/

RUN pip install --no-cache-dir .

# MCP server runs on stdio (no port needed)
CMD ["python3", "scripts/mcp_server.py"]
