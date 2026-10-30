FROM node:22-alpine
RUN addgroup -S aplicacao && adduser -S aplicacao -G aplicacao
USER aplicacao
WORKDIR /app
COPY --chown=aplicacao src ./src
COPY --chown=aplicacao package.json node_modules ./
COPY --chown=aplicacao package.json .
ENV PORT=3000
HEALTHCHECK CMD wget -qO- http://127.0.0.1:3000/health || exit 1
CMD ["node", "src/adaptadores/servidor.mjs"]
