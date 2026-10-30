// Fábrica do verificador C1 (skill contrato-reverso): handler REAL com repositório em memória e
// relógio que avança 1 s por chamada (ordenação "mais novo primeiro" fica observável). Nada de nuvem.
import { criarApp, repositorioEmMemoria } from "../src/handler.mjs";

export function criarHandler() {
  let t = Date.parse("2026-01-01T00:00:00Z");
  return criarApp({ repositorio: repositorioEmMemoria(), relogio: () => new Date((t += 1000)) });
}
