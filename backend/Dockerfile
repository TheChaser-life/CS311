FROM python:3.10-slim

WORKDIR /app

COPY . .

RUN apt-get update && xargs -r apt-get install -y < packages.txt && \
apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["python", "api.py"]