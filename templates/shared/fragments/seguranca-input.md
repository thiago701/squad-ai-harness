## Segurança de entrada e supply chain
Toda entrada externa é não confiável: valide tipo, tamanho, formato e domínio ANTES de usar (value objects validam na construção). Nunca interpolar entrada em comandos/SQL/HTML. Segredos só via ambiente/secret manager — nunca em código, log ou template. Dependências: mínimo necessário, versão pinada, scanner na CI.
