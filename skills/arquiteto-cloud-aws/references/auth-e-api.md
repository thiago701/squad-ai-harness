# Referência — Autenticação e API (Cognito, @HttpExchange, API Gateway)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
## Catálogo de Serviços AWS por Problema

### Autenticação e Autorização — Cognito

**O erro mais comum de times:** implementar gestão de usuários do zero (JWT manual, hash de senha, refresh token, MFA, social login). Cognito resolve tudo isso com zero código de segurança.

```
Cognito User Pool   → registro, login, MFA, email/SMS verification, social login
Cognito Identity Pool → credenciais temporárias AWS para usuários autenticados
Cognito + API Gateway → autorização de APIs sem código de middleware

Quando usar Cognito:
  ✓ Qualquer sistema com usuários (B2C, B2B, interno)
  ✓ Social login (Google, Facebook, Apple)
  ✓ MFA obrigatório por compliance
  ✓ SSO com SAML/OIDC (federação corporativa)

Free tier: 50.000 MAU gratuitos — suficiente para validar qualquer produto
```

```python
# Python — integração com Cognito via boto3 (sem biblioteca de auth própria)
import boto3
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
from jwt.algorithms import RSAAlgorithm
import httpx

class CognitoAuth:
    """Validação de JWT do Cognito — zero código de criptografia próprio."""

    def __init__(self, user_pool_id: str, client_id: str, region: str = "us-east-1"):
        self.user_pool_id = user_pool_id
        self.client_id    = client_id
        self.region       = region
        self._jwks        = None  # carregado lazy

    async def _get_jwks(self) -> dict:
        if self._jwks is None:
            url = f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}/.well-known/jwks.json"
            async with httpx.AsyncClient() as client:
                self._jwks = (await client.get(url)).json()
        return self._jwks

    async def validar_token(self, token: str) -> dict:
        jwks = await self._get_jwks()
        header = jwt.get_unverified_header(token)
        chave_publica = RSAAlgorithm.from_jwk(
            next(k for k in jwks["keys"] if k["kid"] == header["kid"])
        )
        return jwt.decode(
            token,
            chave_publica,
            algorithms=["RS256"],
            audience=self.client_id,
        )

# FastAPI — dependência de autenticação reutilizável
security = HTTPBearer()
cognito  = CognitoAuth(
    user_pool_id=os.environ["COGNITO_USER_POOL_ID"],
    client_id=os.environ["COGNITO_CLIENT_ID"],
)

async def usuario_autenticado(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    try:
        return await cognito.validar_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado")

# Uso nos endpoints — sem nenhum código de segurança extra
@app.get("/pedidos")
async def listar_pedidos(usuario: dict = Depends(usuario_autenticado)):
    user_id = usuario["sub"]
    return pedido_service.listar_por_usuario(user_id)
```

```java
// Java — Spring Boot 4 + Cognito via Spring Security 7 OAuth2
// In Spring Boot 4 / Spring Security 7, @EnableWebSecurity is no longer needed (auto-configured)
// application.yml — zero código de segurança, apenas configuração
/*
spring:
  security:
    oauth2:
      resourceserver:
        jwt:
          issuer-uri: https://cognito-idp.us-east-1.amazonaws.com/${COGNITO_USER_POOL_ID}
          jwk-set-uri: https://cognito-idp.us-east-1.amazonaws.com/${COGNITO_USER_POOL_ID}/.well-known/jwks.json
*/

@Configuration
public class SecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/public/**", "/actuator/health").permitAll()
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2.jwt(Customizer.withDefaults()))
            .sessionManagement(s -> s.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .csrf(CsrfConfigurer::disable)
            .build();
    }

    // Extrai grupos/roles do token Cognito
    @Bean
    public JwtAuthenticationConverter jwtAuthConverter() {
        var converter = new JwtGrantedAuthoritiesConverter();
        converter.setAuthoritiesClaimName("cognito:groups");
        converter.setAuthorityPrefix("ROLE_");
        var authConverter = new JwtAuthenticationConverter();
        authConverter.setJwtGrantedAuthoritiesConverter(converter);
        return authConverter;
    }
}

// Controller — segurança resolvida pelo Spring Security + Cognito, zero código manual
@RestController
@RequestMapping("/pedidos")
public class PedidoController {

    @GetMapping
    public List<PedidoDTO> listar(@AuthenticationPrincipal Jwt jwt) {
        String userId = jwt.getSubject();  // sub do Cognito
        return pedidoService.listarPorUsuario(userId);
    }
}
```

---

### HTTP Service Clients com @HttpExchange (Spring Framework 7)

**Declarar clientes HTTP para APIs externas e serviços AWS sem boilerplate**, usando `@HttpExchange` do Spring Framework 7 + `RestClient.Builder`. Ideal para chamar APIs de CEP, gateways de pagamento, ou serviços internos com propagação automática de **Correlation ID** e resiliência declarativa.

```java
// Java 25 — Interface @HttpExchange para cliente API externa
// Dependência: org.springframework:spring-web (Spring Framework 7+)

@HttpExchange("/api/v1")
public interface CepServiceClient {

    @GetExchange("/cep/{codigo}")
    CepResponse buscarCep(@PathVariable String codigo);

    @PostExchange("/pagamentos")
    PagamentoResponse processarPagamento(@RequestBody PagamentoRequest req);
}

// Configuração centralizada com RestClient.Builder
@Configuration
public class HttpClientsConfig {

    @Bean
    public CepServiceClient cepServiceClient(RestClient.Builder builder) {
        return HttpServiceProxyFactory
            .builder(builder
                .baseUrl("https://api.cep.com.br")
                .requestInterceptor(new CorrelationIdInterceptor())  // ← Injeta X-Correlation-Id
                .build()
            )
            .build()
            .createClient(CepServiceClient.class);
    }
}

// Interceptor que propaga Correlation ID de ScopedValue para header HTTP
@Component
public class CorrelationIdInterceptor implements ClientHttpRequestInterceptor {

    private static final String HEADER = "X-Correlation-Id";

    @Override
    public ClientHttpResponse intercept(HttpRequest request, byte[] body,
                                        ClientHttpRequestExecution execution)
            throws IOException {
        // Lê Correlation ID do ScopedValue (vem do Filter de ingress)
        String correlationId = CorrelationIdContext.currentOrNew();
        request.getHeaders().set(HEADER, correlationId);
        
        log.debug("Propagando Correlation ID: {}", correlationId);
        return execution.execute(request, body);
    }
}

// Service que usa o cliente com @CircuitBreaker e @Retry
@Service
@RequiredArgsConstructor
public class CepService {

    private final CepServiceClient client;

    @CircuitBreaker(name = "cep-lookup", fallbackMethod = "buscarCepFallback")
    @Retry(name = "cep-lookup", fallbackMethod = "buscarCepFallback")
    public CepResponse buscarCep(String codigo) {
        try {
            return client.buscarCep(codigo);
        } catch (Exception e) {
            log.warn("Erro ao buscar CEP {} via API externa", codigo, e);
            throw new CepLookupException("CEP não encontrado", e);
        }
    }

    // Fallback — dados padrão ou erro controlado
    public CepResponse buscarCepFallback(String codigo, Exception ex) {
        log.error("Circuito aberto para CEP. Retornando fallback.", ex);
        return CepResponse.fallback(codigo);
    }
}

// Configuração Resilience4j para o cliente
/*
resilience4j:
  circuitbreaker:
    instances:
      cep-lookup:
        failure-rate-threshold: 50
        wait-duration-in-open-state: 10s
        permitted-number-of-calls-in-half-open-state: 3
        sliding-window-size: 10
  retry:
    instances:
      cep-lookup:
        max-attempts: 3
        wait-duration: 500ms
        retry-exceptions: [java.net.SocketTimeoutException, java.io.IOException]
*/
```

**Teste com MockWebServer ou RestClient test infra:**

```java
@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.NONE)
@ExtendWith(RestClientTest.class)
class CepServiceClientTest {

    private MockWebServer mockServer;

    @BeforeEach
    void setup() throws Exception {
        mockServer = new MockWebServer();
        mockServer.start();
    }

    @Test
    void buscarCep_sucesso() {
        // Arrange
        mockServer.enqueue(new MockResponse()
            .setResponseCode(200)
            .setBody("{\"codigo\":\"01310100\",\"cidade\":\"São Paulo\",\"uf\":\"SP\"}"));

        var client = HttpServiceProxyFactory
            .builder(RestClient.builder()
                .baseUrl(mockServer.url("").toString())
                .build())
            .build()
            .createClient(CepServiceClient.class);

        // Act
        var response = client.buscarCep("01310100");

        // Assert
        assertThat(response.codigo()).isEqualTo("01310100");
        assertThat(response.cidade()).isEqualTo("São Paulo");
    }

    @Test
    void buscarCep_timeout() {
        // Arrange
        mockServer.enqueue(new MockResponse()
            .setResponseCode(504)
            .setBody("{\"erro\":\"Timeout\"}"));

        // Act & Assert
        assertThrows(CepLookupException.class, () -> {
            cepService.buscarCep("01310100");
        });
    }

    @AfterEach
    void tearDown() throws Exception {
        mockServer.shutdown();
    }
}
```

**Benefícios:**
- ✓ **Zero boilerplate**: Interface + anotações = cliente HTTP completo
- ✓ **Correlation ID automático**: ScopedValue propagado sem código manual
- ✓ **Resiliência declarativa**: `@CircuitBreaker` + `@Retry` aplicados ao serviço
- ✓ **Type safety**: Compilação verifica URLs e tipos
- ✓ **Testável**: MockWebServer substitui server real em testes

---

## API Gateway — Especialista Enterprise

> API Gateway tem 3 sabores. Erro #1 das equipes: usar REST API quando HTTP API resolve em 1/3 do custo e 60% menos latência.

### REST vs HTTP vs WebSocket — Matriz Definitiva

| Característica | **REST API** | **HTTP API** | **WebSocket API** |
|----------------|--------------|--------------|--------------------|
| Custo (1M req) | $3.50 | **$1.00** | $1.00 + connection minutes |
| Latência overhead | ~50-100 ms | **~10-30 ms** | < 100ms |
| Throttling | Por API key, usage plan, route | Por route, stage | Por route |
| Custom domain | Sim | Sim | Sim |
| API keys + Usage Plans | **Sim** | Não (use Cognito/JWT) | Não |
| Request validation | OpenAPI, JSON Schema | Limitado | Não |
| Response cache | **Sim (gerenciado)** | Não (use CloudFront) | N/A |
| Mutual TLS | Sim | Sim | Não |
| Lambda authorizer | Sim | Sim (mais simples) | Sim |
| Cognito authorizer | Sim | Sim | Sim |
| JWT authorizer | Não | **Sim (nativo)** | Não |
| VPC Link | Sim (NLB) | Sim (ALB **e** NLB) | Sim |
| Private API (interface endpoint) | Sim | Não | Não |
| OpenAPI import | Sim (3.0) | Sim (3.0) | N/A |
| WAF | **Sim** | Não direto (use CloudFront) | Não |
| Use case | APIs públicas com API keys, B2B com SLA, request validation, response cache | Microservices internas, JWT auth, HTTP/2, 60% mais barato, latência baixa | Chat, real-time updates, gaming, notificações |

**Regra:** **HTTP API por default**. Vá para REST API só quando precisar de API keys + usage plans, response cache nativo, ou WAF direto.

### HTTP API com JWT Authorizer (Cognito)

```java
HttpApi httpApi = HttpApi.Builder.create(this, "OrdersApi")
    .apiName("orders-api")
    .description("Orders microservice API")
    .corsPreflight(CorsPreflightOptions.builder()
        .allowOrigins(List.of("https://app.example.com"))
        .allowMethods(List.of(CorsHttpMethod.GET, CorsHttpMethod.POST, CorsHttpMethod.PUT))
        .allowHeaders(List.of("Authorization", "Content-Type", "X-Correlation-Id"))
        .allowCredentials(true)
        .maxAge(Duration.hours(1))
        .build())
    .createDefaultStage(false)
    .build();

// JWT authorizer com Cognito
HttpJwtAuthorizer jwtAuth = HttpJwtAuthorizer.Builder.create("CognitoAuth",
        "https://cognito-idp.us-east-1.amazonaws.com/" + userPool.getUserPoolId())
    .jwtAudience(List.of(userPoolClient.getUserPoolClientId()))
    .build();

// Stage com throttling
HttpStage stage = HttpStage.Builder.create(this, "ProdStage")
    .httpApi(httpApi)
    .stageName("prod")
    .autoDeploy(true)
    .throttle(ThrottleSettings.builder()
        .rateLimit(10000)                  // 10K RPS sustained
        .burstLimit(20000)                 // 20K RPS burst
        .build())
    .build();

// Rota com VPC Link para ALB privado
VpcLink vpcLink = VpcLink.Builder.create(this, "VpcLink")
    .vpc(vpc)
    .securityGroups(List.of(vpcLinkSg))
    .subnets(SubnetSelection.builder().subnetType(SubnetType.PRIVATE_WITH_EGRESS).build())
    .build();

httpApi.addRoutes(AddRoutesOptions.builder()
    .path("/api/v1/orders/{proxy+}")
    .methods(List.of(HttpMethod.ANY))
    .integration(HttpAlbIntegration.Builder.create("AlbIntegration", listener)
        .vpcLink(vpcLink)
        .method(HttpMethod.ANY)
        .parameterMapping(ParameterMapping.fromObject(Map.of(
            "X-Forwarded-For", MappingValue.requestHeader("X-Forwarded-For"),
            "X-Correlation-Id", MappingValue.requestHeader("X-Correlation-Id")
        )))
        .build())
    .authorizer(jwtAuth)
    .build());
```

### REST API com Usage Plans + API Keys (B2B)

```java
RestApi restApi = RestApi.Builder.create(this, "B2bApi")
    .restApiName("b2b-orders")
    .deployOptions(StageOptions.builder()
        .stageName("v1")
        .throttlingRateLimit(5000)
        .throttlingBurstLimit(10000)
        .cachingEnabled(true)
        .cacheClusterSize("0.5")           // 0.5 GB cache cluster
        .cacheTtl(Duration.minutes(5))
        .metricsEnabled(true)
        .dataTraceEnabled(false)            // NUNCA true em prod (CloudWatch caro)
        .loggingLevel(MethodLoggingLevel.ERROR)
        .accessLogDestination(new LogGroupLogDestination(accessLogs))
        .accessLogFormat(AccessLogFormat.jsonWithStandardFields(JsonWithStandardFieldProps.builder()
            .caller(true).httpMethod(true).ip(true).protocol(true)
            .requestTime(true).resourcePath(true).responseLength(true)
            .status(true).user(true)
            .build()))
        .tracingEnabled(true)               // X-Ray
        .build())
    .build();

// Plans
UsagePlan freePlan = restApi.addUsagePlan("FreePlan", AddUsagePlanOptions.builder()
    .name("free")
    .throttle(ThrottleSettings.builder().rateLimit(10).burstLimit(20).build())
    .quota(QuotaSettings.builder().limit(1000).period(Period.DAY).build())
    .build());

UsagePlan enterprisePlan = restApi.addUsagePlan("EnterprisePlan", AddUsagePlanOptions.builder()
    .name("enterprise")
    .throttle(ThrottleSettings.builder().rateLimit(5000).burstLimit(10000).build())
    .quota(QuotaSettings.builder().limit(10_000_000).period(Period.MONTH).build())
    .build());

freePlan.addApiStage(UsagePlanPerApiStage.builder().stage(restApi.getDeploymentStage()).build());
enterprisePlan.addApiStage(UsagePlanPerApiStage.builder().stage(restApi.getDeploymentStage()).build());

// API Keys
ApiKey enterpriseKey = restApi.addApiKey("AcmeIncKey",
    ApiKeyOptions.builder().apiKeyName("acme-inc-prod").build());
enterprisePlan.addApiKey(enterpriseKey);
```

### Request Validation com OpenAPI 3.0

```yaml
# openapi.yaml
openapi: 3.0.3
info:
  title: Orders API
  version: 1.0.0
paths:
  /orders:
    post:
      x-amazon-apigateway-request-validator: validate-body
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/OrderRequest'
      responses:
        '201':
          description: Created
        '400':
          description: Bad Request
x-amazon-apigateway-request-validators:
  validate-body:
    validateRequestBody: true
    validateRequestParameters: true
components:
  schemas:
    OrderRequest:
      type: object
      required: [customerId, items]
      properties:
        customerId:
          type: string
          format: uuid
        items:
          type: array
          minItems: 1
          maxItems: 100
          items:
            $ref: '#/components/schemas/Item'
    Item:
      type: object
      required: [sku, quantity]
      properties:
        sku:
          type: string
          pattern: '^[A-Z0-9-]+$'
        quantity:
          type: integer
          minimum: 1
          maximum: 999
```

```bash
aws apigateway import-rest-api --body fileb://openapi.yaml --fail-on-warnings
```

**Vantagem:** API Gateway rejeita request inválida **antes** de invocar Lambda/ALB. Economia de custo + proteção contra payloads maliciosos.

### Response Caching (REST API)

```java
Method method = ordersResource.addMethod("GET",
    new LambdaIntegration(getOrdersFunction),
    MethodOptions.builder()
        .apiKeyRequired(true)
        .methodResponses(List.of(MethodResponse.builder().statusCode("200").build()))
        .requestParameters(Map.of(
            "method.request.querystring.customerId", true,
            "method.request.querystring.status", false
        ))
        .build());

// Cache key parameters (importantes!)
CfnMethod cfnMethod = (CfnMethod) method.getNode().getDefaultChild();
cfnMethod.setIntegration(CfnMethod.IntegrationProperty.builder()
    .cacheKeyParameters(List.of(
        "method.request.querystring.customerId",
        "method.request.querystring.status"
    ))
    .cacheNamespace("orders-cache")
    .build());
```

**TTL recomendado:** 60s para listagens dinâmicas, 300s para read-mostly, 3600s para read-only quase imutável.

### Mutual TLS para B2B

```java
DomainName customDomain = DomainName.Builder.create(this, "CustomDomain")
    .domainName("api.example.com")
    .certificate(cert)
    .endpointType(EndpointType.REGIONAL)
    .securityPolicy(SecurityPolicy.TLS_1_2)
    .mtls(MTLSConfig.builder()
        .bucket(trustBucket)              // bucket S3 com truststore.pem
        .key("truststore.pem")
        .version("1")
        .build())
    .build();
```

---

