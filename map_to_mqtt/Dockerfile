FROM python:3.12-alpine

WORKDIR /app
EXPOSE 8080

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["python3", "-u", "-m", "app.main"]
