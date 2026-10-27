FROM python:3.11-slim
WORKDIR /app
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY packages/ ./packages/
COPY apps/api/ ./apps/api/
ENV PYTHONPATH=/app:/app/packages/trace:/app/packages/agent-core:/app/packages/tools:/app/packages/agent_core
WORKDIR /app/apps/api
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
