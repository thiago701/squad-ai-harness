FROM python:3.13-slim AS build
WORKDIR /app
COPY src ./src
FROM python:3.13-slim
RUN useradd --create-home aplicacao
USER aplicacao
WORKDIR /app
COPY --from=build /app/src ./src
ENV PYTHONPATH=/app/src
HEALTHCHECK CMD python -c "import taskbox" || exit 1
ENTRYPOINT ["python", "-m", "taskbox.adaptadores.cli"]
CMD ["listar"]
