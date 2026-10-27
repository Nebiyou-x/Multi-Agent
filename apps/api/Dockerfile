FROM python:3.11-slim
WORKDIR /app
RUN pip install fastapi uvicorn psycopg2-binary redis pydantic
COPY ./main.py ./main.py
COPY ../../packages ./packages
ENV PYTHONPATH=/app:/app/packages/trace/src
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]