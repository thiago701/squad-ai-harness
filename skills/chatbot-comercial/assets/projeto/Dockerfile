# Imagem única, sem servidor de aplicação externo. Deploy isolado por cliente:
# um container + um volume por tenant.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# squad-ai-core: vendorizado por `scaffold.py --core-core ../squad-ai-core` (build offline) ou,
# em produção, resolvido pelo índice privado.
COPY vendor /opt/vendor
RUN if [ -d /opt/vendor/squad-ai-core ]; then pip install /opt/vendor/squad-ai-core; \
    else pip install squad-ai-core; fi

COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
COPY verticais ./verticais
COPY dados ./dados
COPY golden ./golden
RUN pip install .

RUN useradd --create-home --uid 10001 chatbot && \
    mkdir -p /app/var && chown -R chatbot:chatbot /app
USER chatbot

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/saude', timeout=4).status==200 else 1)"

CMD ["python", "-m", "app.main"]
