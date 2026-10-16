FROM python:3.11.2-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY main.py ./main.py
COPY market_agent ./market_agent
COPY sample_data ./sample_data

RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p reports data \
    && chown -R appuser:appuser /app

USER appuser

ENTRYPOINT ["python", "main.py"]
CMD ["run-once"]
