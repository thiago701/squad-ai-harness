// Borda HTTP: rotas finas + UM handler central de erros (dominio -> status).
import { createServer } from "node:http";
import { Tarefas } from "../dominio/colecao.mjs";
import { ErroDeDominio, TarefaInexistente, TituloInvalido } from "../dominio/tarefa.mjs";
import { ServicoDeTarefas } from "../aplicacao/servico.mjs";
import { registrar } from "./registro.mjs";

const LIMITE_BODY = 16 * 1024;

export function criarAplicacao() {
  const servico = new ServicoDeTarefas(new Tarefas());
  return createServer((requisicao, resposta) => {
    tratar(servico, requisicao, resposta).catch((erro) => responderErro(resposta, erro));
  });
}

async function tratar(servico, requisicao, resposta) {
  const rota = `${requisicao.method} ${requisicao.url}`;
  if (rota === "GET /health") return responderJson(resposta, 200, { situacao: "ok" });
  if (rota === "GET /tarefas") return responderJson(resposta, 200, servico.pendentes());
  if (rota === "POST /tarefas") return criar(servico, requisicao, resposta);
  if (requisicao.method === "POST" && /^\/tarefas\/[^/]+\/concluir$/.test(requisicao.url)) {
    const identificador = requisicao.url.split("/")[2];
    return responderJson(resposta, 200, { tarefa: servico.concluir(identificador) });
  }
  return responderJson(resposta, 404, { erro: "rota desconhecida" });
}

async function criar(servico, requisicao, resposta) {
  const corpo = await lerJson(requisicao);
  const identificador = servico.criar(corpo.titulo);
  responderJson(resposta, 201, { identificador });
}

async function lerJson(requisicao) {
  let tamanho = 0;
  const partes = [];
  for await (const parte of requisicao) {
    tamanho += parte.length;
    if (tamanho > LIMITE_BODY) throw new TituloInvalido("body excede limite");
    partes.push(parte);
  }
  try {
    return JSON.parse(Buffer.concat(partes).toString("utf-8") || "{}");
  } catch {
    throw new TituloInvalido("JSON invalido");
  }
}

function statusDe(erro) {
  if (erro instanceof TarefaInexistente) return 404;
  if (erro instanceof ErroDeDominio) return 422;
  return 500;
}

function responderErro(resposta, erro) {
  const status = statusDe(erro);
  registrar(status >= 500 ? "erro" : "aviso", erro.message, { status });
  responderJson(resposta, status, { erro: erro.message });
}

function responderJson(resposta, status, corpo) {
  resposta.writeHead(status, { "content-type": "application/json" });
  resposta.end(JSON.stringify(corpo));
}

if (process.argv[1] && process.argv[1].endsWith("http.mjs")) {
  const porta = Number(process.env.PORT ?? 3000);
  criarAplicacao().listen(porta, () => registrar("info", "servidor ativo", { porta }));
}
