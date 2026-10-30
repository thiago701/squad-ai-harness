import { criarAplicacao } from "./api.mjs";

const aplicacao = criarAplicacao({ logger: true });
const porta = Number(process.env.PORT ?? 3000);
aplicacao.listen({ port: porta, host: "0.0.0.0" });
