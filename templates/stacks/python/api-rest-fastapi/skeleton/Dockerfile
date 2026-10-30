FROM python:3.13-slim
RUN useradd --create-home aplicacao && pip install --no-cache-dir "fastapi>=0.139" "uvicorn>=0.30"
USER aplicacao
WORKDIR /app
COPY --chown=aplicacao src ./src
ENV PYTHONPATH=/app/src
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/health')" || exit 1
CMD ["python", "-m", "uvicorn", "taskbox_api.adaptadores.api:aplicacao", "--host", "0.0.0.0", "--port", "8000"]
