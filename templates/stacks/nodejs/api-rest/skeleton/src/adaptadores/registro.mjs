// Logging estruturado minimo (JSON em stdout), sem dependencias.
export function registrar(nivel, mensagem, extras = {}) {
  const corpo = { nivel, quando: new Date().toISOString(), mensagem, ...extras };
  console.log(JSON.stringify(corpo));
}
