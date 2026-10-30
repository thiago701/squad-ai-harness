## Tratamento de erros
Erros de domínio são tipos dedicados (não strings soltas): distinguíveis, testáveis, com mensagem para humanos. Um handler central por borda (HTTP/CLI/worker) traduz erro → resposta; nada de catch silencioso. Falha de infraestrutura ≠ erro de domínio: retry/resiliência só na borda de infraestrutura.
