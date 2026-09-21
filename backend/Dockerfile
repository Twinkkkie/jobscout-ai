FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Keep dependency installation in its own cached layer. Application source
# changes should not force Docker to contact PyPI on every rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /app/uploads

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8030"]
