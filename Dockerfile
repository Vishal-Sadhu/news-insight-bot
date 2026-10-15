FROM python:3.11.2-slim

WORKDIR /app
COPY requirements.txt requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["python", "main.py"]
