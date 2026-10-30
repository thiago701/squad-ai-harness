// FIXTURE SINTÉTICA — tudo aqui está ERRADO de propósito (selftest da lente LOG-xx).
// Versão correta: ../bom/handler.ts
export const handler = async (event: any) => {
  const token = event.headers?.authorization;
  console.log(`token=${token}`);                        // LOG-01
  console.log("evento recebido", event.body);           // LOG-13
  console.log("cliente", { cpf: event.cpf, email: event.email }); // LOG-02
  return { statusCode: 200 };
};
