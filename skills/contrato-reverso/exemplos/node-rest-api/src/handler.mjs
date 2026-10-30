// Exemplo mínimo: Lambda Node.js 22 atrás de REST API (v1, payload 1.0) com autorizador Cognito.
// Serve de caso de validação do C1 Node da skill contrato-reverso (runner Node + Gateway simulado).
import { randomUUID } from "node:crypto";

const ORIGENS = (process.env.ORIGENS_PERMITIDAS || "https://web.exemplo.local").split(",");

export function criarApp({ repositorio, relogio = () => new Date() }) {
  const resposta = (status, corpo, origem) => ({
    statusCode: status,
    headers: {
      "Content-Type": status >= 400 ? "application/problem+json" : "application/json",
      // REST API com proxy: o Gateway NÃO acrescenta CORS na resposta real — é papel do Lambda.
      ...(ORIGENS.includes(origem) ? { "Access-Control-Allow-Origin": origem, Vary: "Origin" } : {}),
    },
    body: corpo === undefined ? "" : JSON.stringify(corpo),
  });
  const problema = (status, titulo, origem) => resposta(status, { type: `https://exemplo.local/problemas/${status}`, title: titulo, status }, origem);

  return async (evento) => {
    const origem = (evento.headers || {}).origin || (evento.headers || {}).Origin;
    const dono = evento.requestContext?.authorizer?.claims?.sub;
    if (!dono) return problema(401, "Não autenticado", origem);
    const id = evento.pathParameters?.id;
    const rota = `${evento.httpMethod} ${evento.resource}`;
    if (rota === "POST /itens") {
      let corpo;
      try { corpo = JSON.parse(evento.body || "{}"); } catch { return problema(400, "JSON inválido", origem); }
      if (typeof corpo.nome !== "string" || !corpo.nome.trim()) return problema(422, "nome obrigatório", origem);
      const item = { id: randomUUID(), dono, nome: corpo.nome.trim(), quantidade: corpo.quantidade ?? 1, criadoEm: relogio().toISOString() };
      await repositorio.salvar(item);
      return resposta(201, item, origem);
    }
    if (rota === "GET /itens") {
      const itens = (await repositorio.doDono(dono)).sort((a, b) => b.criadoEm.localeCompare(a.criadoEm));
      return resposta(200, { itens, total: itens.length }, origem);
    }
    if (rota === "GET /itens/{id}" || rota === "DELETE /itens/{id}") {
      const item = await repositorio.porId(id);
      if (!item || item.dono !== dono) return problema(404, "Item não encontrado", origem); // nunca 403
      if (evento.httpMethod === "DELETE") { await repositorio.remover(id); return resposta(204, undefined, origem); }
      return resposta(200, item, origem);
    }
    return problema(404, "Rota não encontrada", origem);
  };
}

export function repositorioEmMemoria() {
  const dados = new Map();
  return {
    salvar: async (i) => { dados.set(i.id, i); },
    porId: async (id) => dados.get(id),
    doDono: async (d) => [...dados.values()].filter((i) => i.dono === d),
    remover: async (id) => { dados.delete(id); },
  };
}

// Handler de produção usaria um repositório DynamoDB; o exemplo usa memória.
export const handler = criarApp({ repositorio: repositorioEmMemoria() });
