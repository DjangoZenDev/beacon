FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY page-service/ ./page-service/
COPY core/ ./core/
CMD ["python", "-m", "page-service.server"]
