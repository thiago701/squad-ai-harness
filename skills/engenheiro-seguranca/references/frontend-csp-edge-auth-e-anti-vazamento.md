# Segurança de SPA Estática (CSP A+ Zero-`innerHTML`), Auth na Borda (CloudFront + KVS) e Scanner Anti-Vazamento por Digest SHA-256

> **Origem:** auditoria de segurança e hardening profissional do projeto *Consolidador de Treinamentos* (out/2026).
> **Vínculos:** `LL-0026`, `LL-0027`, `LL-0028`, `LL-0030`, `LL-0037`, `LL-0041`, `LL-0043` · `instinto-0013`, `instinto-0014`, `instinto-0015`, `instinto-0019`.

---

## 1. SPA Estática com CSP Grau A+ (`Zero-innerHTML` e `Zero-Inline-Style`)

Aplicações frontend sem framework pesado (Vanilla JS) frequentemente caem na armadilha de usar `innerHTML` com template literals e `element.style.width = ...`, o que abre brechas de **DOM XSS** e obriga a incluir `'unsafe-inline'` na `Content-Security-Policy`.

### 1.1. Política CSP Alvo (Response Headers Policy no CloudFront)
```http
Content-Security-Policy: default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data: blob:; font-src 'self'; connect-src 'self'; frame-src 'self' blob:; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'; upgrade-insecure-requests
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Strict-Transport-Security: max-age=63072000; includeSubDomains; preload
```

### 1.2. Fábrica Segura de DOM (`domEl`) — Banimento Total de `innerHTML`
- **Proibido no código:** `.innerHTML`, `.outerHTML`, `.insertAdjacentHTML()`, `document.write()`, `eval()`, `new Function()`.
- **Padrão obrigatório:** construir todo elemento via helper `domEl(tag, attrs, children)` que usa exclusivamente `document.createElement`, `setAttribute` (com whitelist de atributos) e `document.createTextNode` / `textContent`:
  ```javascript
  function domEl(tag, attrs, children) {
    const el = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (v === undefined || v === null || v === false) continue;
        if (k === 'className') el.className = String(v);
        else if (k === 'textContent') el.textContent = String(v);
        else if (k === 'dataset') {
          for (const [dk, dv] of Object.entries(v)) el.dataset[dk] = String(dv);
        } else if (k.startsWith('on') && typeof v === 'function') {
          el.addEventListener(k.slice(2).toLowerCase(), v);
        } else if (v === true) el.setAttribute(k, '');
        else el.setAttribute(k, String(v));
      }
    }
    if (children != null) {
      const list = Array.isArray(children) ? children : [children];
      for (const c of list) {
        if (c == null || c === false) continue;
        el.appendChild(typeof c === 'node' || c instanceof Node ? c : document.createTextNode(String(c)));
      }
    }
    return el;
  }
  ```

### 1.3. Eliminação de `style=` Inline para Barras de Progresso e Animações
- Sob `style-src 'self'`, qualquer `el.style.width = '75%'` ou `el.setAttribute('style', ...)` é **bloqueado pelo navegador**!
- **Solução compatível com CSP estrita:** gerar no CSS estático (`styles.css`) as classes discretas `.w-pct-0` até `.w-pct-100` definindo a custom property `--pct: N`:
  ```css
  .w-pct-0 { width: 0%; --pct: 0; }
  /* ... */
  .w-pct-100 { width: 100%; --pct: 100; }
  ```
- O componente visual usa `calc(var(--pct, 0) * 1%)` no `background-position` de um gradiente `0% vermelho → 50% âmbar → 100% verde`, permitindo barras de progresso animadas com **zero estilo inline**.

---

## 2. Validação de Upload no Cliente: Magic Bytes + Sanitização de Nome

Nunca confie apenas na extensão do arquivo (`.pdf`, `.png`) ou no `file.type` informado pelo SO:
1. **Verificação de Assinatura Binária (Magic Bytes):** ler os primeiros 8 bytes com `FileReader.readAsArrayBuffer(file.slice(0, 8))` antes de aceitar o arquivo:
   - **PDF:** `25 50 44 46 2D` (`%PDF-`)
   - **PNG:** `89 50 4E 47 0D 0A 1A 0A`
   - **JPEG:** `FF D8 FF`
   - **BMP:** `42 4D` (`BM`)
2. **Sanitização de Nome de Arquivo:** remover caracteres de controle (`[\x00-\x1F\x7F]`), sequências de path traversal (`..`, `/`, `\`) e limitar a 180 caracteres.
3. **Allowlist de URLs de Evidência:** validar protocolo `https:` via `new URL()` e exigir hostname na allowlist corporativa ancorada (`sharepoint.com`, `1drv.ms`, `onedrive.live.com`, `credly.com`, `accredible.com`), bloqueando qualquer URL interna de cliente bancário.

---

## 3. Segurança na Borda: CloudFront Functions + KVS (Sessão, CSRF e RBAC)

Quando a autenticação e autorização rodam numa CloudFront Function (`viewer-request`):
1. **Cookie `__Host-` assinado com HMAC-SHA256:**
   - Prefixo `__Host-` exige `Secure; Path=/` e ausência de atributo `Domain`, impedindo cookie tossing por subdomínios.
   - Comparação de digest e HMAC em **tempo constante** (`constantTimeEqual`) para mitigar timing attacks.
2. **Proteção CSRF em Rotas Virtuais `GET` (`/auth/corp-*`):**
   - Como o Default Cache Behavior do CloudFront só aceita `GET/HEAD/OPTIONS`, ações de borda (como `/auth/corp-trocar-senha` e `/auth/corp-logout`) usam `GET` mas exigem obrigatoriamente:
     - `Sec-Fetch-Site` igual a `same-origin` ou `same-site` (se presente);
     - Header customizado `X-Requested-With: XMLHttpRequest` (que não pode ser enviado por navegação `<a href>`, `<img>` ou `<form>` cross-site sem preflight CORS).
   - Respostas de `/auth/*` sempre retornam `Cache-Control: no-store, no-cache, must-revalidate, private`.
3. **RBAC na Borda sem Vazar Identificadores no Código:**
   - Para restringir um Read Model sensível no S3 (ex.: `/data/relatorio-gestor.json`) apenas ao gestor sem escrever o nome ou a funcional SAP do gestor em texto claro no código versionado:
     - Compare `sha256Hex(colabId)` e `sha256Hex(funcional)` contra os hashes SHA-256 autorizados dentro da função `checkIsGestor`.
     - Retorne `403 Forbidden` na borda antes de tocar no S3.

---

## 4. Minimização LGPD em Pastas Corporativas Compartilhadas (`LL-0026`)

Ao ingerir ou espelhar pastas corporativas compartilhadas (OneDrive/SharePoint) para a nuvem:
- **Diagnóstico obrigatório antes do upload:** no caso real, **85,8% dos arquivos (`3.236` de `3.958` binários = `825,65 MB`)** nas pastas compartilhadas pertenciam a colaboradores de **outras equipes** fora do escopo do sistema!
- **Filtro Estrito de Pertencimento (Allowlist do Roster):** o script de sincronização (`sync_onedrive_s3.py`) só pode enviar para o S3 arquivos cujo colaborador foi casado com confiança no roster da equipe ou que estejam na fila de revisão da equipe. Arquivos de terceiros são contabilizados apenas como métrica agregada (`ignorados_outras_equipes`) e jamais saem da máquina local.

---

## 5. Scanner Anti-Vazamento no Git por Digest SHA-256 (`Inv.9` — `LL-0028`)

### O Paradoxo do Scanner de Segredos Versionado
Se você cria um script `check_invariantes.py` versionado num repositório Git público para proibir que o AWS Account ID real (`12 dígitos`), o CloudFront Distribution ID, a funcional SAP real ou o username do Windows apareçam no código, **colocar esses valores literais na lista negra do script vaza os próprios valores no Git!**

### A Solução: Lista Negra por Digest SHA-256
1. No script versionado, armazene **apenas os digests SHA-256** (com contexto/descrição genérica) dos tokens proibidos:
   ```python
   FORBIDDEN_TOKEN_SHA256 = {
       "e831a575...": "Username local do sistema operacional",
       "479b69a0...": "ID de distribuição CloudFront real (Sandbox)",
       "be5f412e...": "AWS Account ID real (Sandbox)",
       "61051361...": "AWS Account ID real (Produção)",
       "f1c83692...": "Matrícula funcional real (Gestor)",
   }
   ```
2. O scanner tokeniza cada arquivo rastreado pelo `git ls-files` (`re.findall(r"[A-Za-z0-9_-]{4,64}", text)`), calcula `hashlib.sha256(token.encode("utf-8")).hexdigest()` (e `.lower()`) e bloqueia o commit se houver qualquer colisão com `FORBIDDEN_TOKEN_SHA256`.
3. Dessa forma, o repositório permanece **100% auditável e zero-knowledge** quanto aos identificadores sensíveis reais.

---

## 6. Validação de Parâmetros de Arquivo na Borda (`ARQ_RE`): Anti-Path-Traversal Compatível com UTF-8 (`LL-0037`)

Ao validar nomes de arquivos em endpoints de visualização/download na CloudFront Function (`/api/certificados/visualizar?arquivo=...`):
- **Erro comum:** usar whitelist restrita a ASCII (`/^[A-Za-z0-9._ -]+\.pdf$/i`), o que quebra nomes canônicos em português contendo acentos UTF-8 (`Introdução`, `Gonçalo`), parênteses `( )` ou vírgulas `,`.
- **Regra Segura:** combinar **blacklist explícita de caracteres perigosos** (`\x00-\x1f`, `/`, `\`, `<`, `>`, `:`, `"`, `|`, `?`, `*`), **rejeição de `..`** (`arq.indexOf('..') !== -1`) e **ancoragem de extensão permitida**:
  ```javascript
  var ARQ_RE = /^[^\x00-\x1f\/\\<>:"|?*]{3,220}\.(pdf|png|jpg|jpeg|bmp)$/i;
  if (!arq || arq.indexOf('..') !== -1 || !ARQ_RE.test(arq)) {
    return jsonResp(400, '{"versao":1,"erro":"parametro_invalido"}');
  }
  ```

---

## 7. Autenticação no Frontend e Memorização Segura de Credenciais — OWASP ASVS V2.1.11 & NIST SP 800-63B (`LL-0041`)

1. **Proibição de Anti-Patterns que Sabotam Gerenciadores de Senha:**
   - **Nunca** coloque campos de login em `<div>` soltos sem `<form>`;
   - **Nunca** use `<input type="text">` mascarado com `-webkit-text-security: disc`, `autocomplete="off"` ou `data-lpignore="true"`;
   - **Nunca** limpe `passInp.value = ""` antes da resposta `200 OK` do servidor de autenticação (gerenciadores nativos leem o valor no momento do sucesso).
2. **Contrato Semântico Obrigatório:**
   - `<form id="corp-auth-gate-form" action="/auth/corp-status" method="post" autocomplete="on">`;
   - Campo usuário: `name="username" autocomplete="username"`;
   - Campo senha: `type="password" name="password" autocomplete="current-password"` + botão de alternância explícito (`toggleAuthGatePasswordVisibility` com `aria-pressed`);
   - Integração com `navigator.credentials.store(new window.PasswordCredential({ id, password, name }))` após login `200 OK`;
   - **Zero Senha em Web Storage:** persista em `localStorage` **apenas** o identificador público (`ntt_remembered_user`) e a flag (`ntt_remember_login`), jamais a senha ou o header `Authorization`.

---

## 8. Ortogonalidade RBAC (`PermissionBus`) e Autenticação Multi-Cliente por Escopo em APIs A2A/MCP (`LL-0041` / `LL-0043`)

1. **Separação Estrita entre `perfil` de Domínio e `papel` RBAC (`LL-0041`):**
   - Nunca sobrecarregue o campo de domínio `perfil` (`DEV_QA`, `LIDER_TECNICO`, `ESPECIALISTA_NEGOCIOS`, `EXECUTIVO` — usado para calcular elegibilidade de cursos) com papéis de controle de acesso (`GESTOR`, `COLABORADOR`, `COLABORADOR_ADMIN`).
   - No `PermissionBus`, bloqueie qualquer tentativa de um papel não-`GESTOR` selecionar, editar, excluir ou promover um registro de `GESTOR` (`canPermission` retorna `false` se `ctx.targetColab` for Gestor ou `ctx.newPerfil === "GESTOR"`).
2. **Autenticação por Consumidor e Isolamento de Escopo em Integrações A2A/MCP (`LL-0043`):**
   - Em endpoints de fornecimento de dados para outros sistemas (`POST /integracao/auditoria-360` e servidor MCP), exija `clientId` + `apiKey`, valide se o cliente está `ativo: true` e se o escopo requisitado consta em `escopos[]` do cliente, e garanta que nenhum segredo (`apiKey`, `SecretString`) ecoe em logs ou respostas.
