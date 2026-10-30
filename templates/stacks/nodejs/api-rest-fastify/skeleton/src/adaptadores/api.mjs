// Borda Fastify 5: JSON Schema valida na rota; erro de dominio no handler central.
import Fastify from "fastify";
import { Tarefas } from "../dominio/colecao.mjs";
import { ErroDeDominio, TarefaInexistente } from "../dominio/tarefa.mjs";
import { ServicoDeTarefas } from "../aplicacao/servico.mjs";

const esquemaNovaTarefa = {
  body: {
    type: "object",
    required: ["titulo"],
    additionalProperties: false,
    properties: { titulo: { type: "string", minLength: 1, maxLength: 200 } },
  },
};

export function criarAplicacao(opcoes = {}) {
  const aplicacao = Fastify({ logger: opcoes.logger ?? false, bodyLimit: 16 * 1024 });
  const servico = new ServicoDeTarefas(new Tarefas());
  registrarRotas(aplicacao, servico);
  registrarErros(aplicacao);
  return aplicacao;
}

function registrarRotas(aplicacao, servico) {
  aplicacao.get("/health", async () => ({ situacao: "ok" }));
  aplicacao.get("/tarefas", async () => servico.pendentes());
  aplicacao.post("/tarefas", { schema: esquemaNovaTarefa }, async (pedido, resposta) => {
    const identificador = servico.criar(pedido.body.titulo);
    return resposta.code(201).send({ identificador });
  });
  aplicacao.post("/tarefas/:identificador/concluir", async (pedido) => ({
    tarefa: servico.concluir(pedido.params.identificador),
  }));
}

function registrarErros(aplicacao) {
  aplicacao.setErrorHandler((erro, pedido, resposta) => {
    if (erro instanceof TarefaInexistente) return resposta.code(404).send({ erro: erro.message });
    if (erro instanceof ErroDeDominio) return resposta.code(422).send({ erro: erro.message });
    if (erro.validation) return resposta.code(400).send({ erro: "entrada invalida" });
    pedido.log.error(erro);
    return resposta.code(500).send({ erro: "falha interna" });
  });
}
