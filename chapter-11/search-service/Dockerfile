FROM python:3.12-slim
WORKDIR /app
COPY search-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY search-service/ .
CMD ["python", "consumer.py"]
