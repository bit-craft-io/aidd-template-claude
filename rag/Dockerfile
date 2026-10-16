FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-mcp.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-mcp.txt
COPY rag.py mcp_server.py ./
EXPOSE 8000
CMD ["python", "mcp_server.py"]
