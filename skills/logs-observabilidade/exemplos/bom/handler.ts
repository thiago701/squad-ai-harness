// Versão CORRETA do ../ruim/handler.ts — logger estruturado (Powertools for TypeScript), campos escolhidos.
import { Logger } from "@aws-lambda-powertools/logger";

const logger = new Logger({ serviceName: "pedidos" });

export const handler = async (event: any) => {
  logger.addContext(event); // request_id, cold_start, function_name
  logger.info("http.request.recebido", {
    metodo: event.requestContext?.http?.method,
    rota: event.rawPath,
    tamanho_bytes: event.body?.length ?? 0,
    cliente_id: event.clienteId,
  });
  return { statusCode: 200 };
};
