# Referência — Proteção de Borda — CORS + Rate Limiting (whitelist de origins, Resilience4j, Spring Cloud Gateway, teste 429)

> Parte da skill `engenheiro-seguranca`. Carregue sob demanda. Hub: `../SKILL.md`.
## Spring Security 7 — CORS + Rate Limiting

### CORS explícito com whitelist de origins (nunca `*` em produção)

A vulnerabilidade clássica é configurar `.allowedOrigins("*")` que expõe a aplicação a **CSRF por cross-origin** e vazamento de dados sensíveis. A solução canônica Spring Boot 4 / Spring Security 7:

```java
// Java 25 — Configuração CORS blindada com whitelist
@Configuration
public class CorsSecurityConfig {

    @Bean
    public SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
        return http
            .cors(cors -> cors.configurationSource(corsConfigurationSource()))
            .csrf(csrf -> csrf.csrfTokenRepository(CookieCsrfTokenRepository.withHttpOnlyFalse()))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/actuator/health", "/actuator/health/live").permitAll()
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth -> oauth.jwt(Customizer.withDefaults()))
            .build();
    }

    @Bean
    public CorsConfigurationSource corsConfigurationSource() {
        var corsConfig = new CorsConfiguration();
        
        // WHITELIST RIGOROSA — nunca usar "*"
        corsConfig.setAllowedOrigins(List.of(
            "https://frontend.example.com",
            "https://app.example.com",
            "https://staging.example.com"
        ));
        
        // Métodos HTTP permitidos (lista branca, não "todas as requisições")
        corsConfig.setAllowedMethods(List.of("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        
        // Headers que o cliente pode enviar
        corsConfig.setAllowedHeaders(List.of(
            "Content-Type",
            "Authorization",
            "X-Correlation-Id",
            "X-Request-Id"
        ));
        
        // Headers que o servidor expõe ao cliente
        corsConfig.setExposedHeaders(List.of(
            "X-Correlation-Id",
            "X-Total-Count",  // para paginação
            "X-Page-Number"
        ));
        
        // Credenciais (cookies, auth headers) — TRUE permite CORS com credenciais
        corsConfig.setAllowCredentials(true);
        
        // Cache de preflight requests — em segundos
        corsConfig.setMaxAge(3600L);

        var source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/api/**", corsConfig);
        return source;
    }
}
```

**Anti-padrão nomeado:**
```java
// VIOLAÇÃO CRÍTICA — 🔴 BLOQUEANTE
corsConfig.setAllowedOrigins(Arrays.asList("*"));  // NUNCA em produção!
corsConfig.setAllowedMethods(Arrays.asList("*"));  // NUNCA!
corsConfig.setAllowedHeaders(Arrays.asList("*"));  // NUNCA!
```

### Rate Limiting com Resilience4j — proteção contra brute force e DoS

```xml
<!-- pom.xml — Apache Maven 4 -->
<dependency>
    <groupId>io.github.resilience4j</groupId>
    <artifactId>resilience4j-spring-boot3</artifactId>
    <version>2.1.0</version>
</dependency>
<dependency>
    <groupId>io.github.resilience4j</groupId>
    <artifactId>resilience4j-ratelimiter</artifactId>
    <version>2.1.0</version>
</dependency>
<dependency>
    <groupId>io.micrometer</groupId>
    <artifactId>micrometer-registry-prometheus</artifactId>
</dependency>
```

```yaml
# application-prod.yml — Configuração Rate Limiting por severidade
resilience4j:
  ratelimiter:
    instances:
      # Endpoint público — limite mais rigoroso
      api-public:
        limit-for-period: 10
        limit-refresh-period: 1s
        timeout-duration: 0ms
        event-consumer-buffer-size: 100
      
      # Endpoint autenticado — limite moderado
      api-auth:
        limit-for-period: 100
        limit-refresh-period: 1s
        timeout-duration: 0ms
      
      # Endpoint crítico (login, pagamento) — limite severo
      api-auth-critico:
        limit-for-period: 3
        limit-refresh-period: 60s
        timeout-duration: 0ms
      
      # Bulk operations — limite baixo
      api-bulk:
        limit-for-period: 5
        limit-refresh-period: 60s
        timeout-duration: 0ms

management:
  endpoints:
    web:
      exposure:
        include: health,metrics,prometheus
```

```java
// Controller com @RateLimiter aplicado
@RestController
@RequestMapping("/api")
public class PedidoController {

    // Endpoint público com rate limit severo
    @GetMapping("/pedidos/publico")
    @RateLimiter(name = "api-public", fallbackMethod = "fallbackPublico")
    public ResponseEntity<List<PedidoDTO>> listarPublico() {
        return ResponseEntity.ok(pedidos);
    }

    // Endpoint autenticado com rate limit moderado
    @PostMapping("/pedidos/confirmar")
    @RateLimiter(name = "api-auth", fallbackMethod = "fallbackAuth")
    @PreAuthorize("hasRole('USER')")
    public ResponseEntity<PedidoDTO> confirmar(@RequestBody ConfirmarPedidoRequest req) {
        var resultado = usecase.executar(req.pedidoId());
        return ResponseEntity.ok(PedidoDTO.from(resultado));
    }

    // Endpoint crítico com rate limit severo (máx 3 tentativas/minuto)
    @PostMapping("/auth/login")
    @RateLimiter(name = "api-auth-critico", fallbackMethod = "fallbackCritico")
    public ResponseEntity<TokenDTO> login(@RequestBody LoginRequest req) {
        var token = authService.authenticate(req.email(), req.senha());
        return ResponseEntity.ok(new TokenDTO(token.accessToken(), token.refreshToken()));
    }

    // Fallback methods — chamados quando rate limit é atingido
    public ResponseEntity<String> fallbackPublico(RequestRateLimiterException e) {
        return ResponseEntity
            .status(HttpStatus.TOO_MANY_REQUESTS)
            .header("Retry-After", "1")
            .body("{\"erro\": \"limite de requisições atingido; tente novamente em 1 segundo\"}");
    }

    public ResponseEntity<String> fallbackAuth(RequestRateLimiterException e) {
        return ResponseEntity
            .status(HttpStatus.TOO_MANY_REQUESTS)
            .header("Retry-After", "5")
            .body("{\"erro\": \"limite de requisições atingido\"}");
    }

    public ResponseEntity<String> fallbackCritico(RequestRateLimiterException e) {
        // Log com audit trail — possível ataque
        log.warn("Rate limit crítico atingido - possível brute force", 
            Map.of("endpoint", "/auth/login", "timestamp", Instant.now()));
        return ResponseEntity
            .status(HttpStatus.TOO_MANY_REQUESTS)
            .header("Retry-After", "60")
            .body("{\"erro\": \"muitas tentativas de login; aguarde 60 segundos\"}");
    }
}
```

### Alternativa: Spring Cloud Gateway com RequestRateLimiter e Redis

Para sistemas distribuídos com múltiplas instâncias, o rate limit **deve ser centralizado em Redis**:

```xml
<!-- pom.xml — Spring Cloud Gateway -->
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-gateway</artifactId>
</dependency>
<dependency>
    <groupId>org.springframework.cloud</groupId>
    <artifactId>spring-cloud-starter-redis-reactive</artifactId>
</dependency>
```

```yaml
# gateway/application-prod.yml
spring:
  cloud:
    gateway:
      routes:
        # Rota 1 — API pública com rate limit severo
        - id: api-public-route
          uri: http://backend-service:8080
          predicates:
            - Path=/api/public/**
          filters:
            - name: RequestRateLimiter
              args:
                redis-rate-limiter:
                  replenish-rate: 10          # 10 requisições
                  requested-tokens: 1          # por
                  burstCapacity: 15            # permite picos de 15
                key-resolver: "#{@ipAddressKeyResolver}"  # por IP
            - name: CircuitBreaker
              args:
                name: apiPublic
                fallbackUri: forward:/fallback/api-public

        # Rota 2 — Auth crítico com rate limit centralizado
        - id: auth-route
          uri: http://backend-service:8080
          predicates:
            - Path=/api/auth/login
          filters:
            - name: RequestRateLimiter
              args:
                redis-rate-limiter:
                  replenish-rate: 3           # 3 tentativas
                  requested-tokens: 1
                  burstCapacity: 5
                key-resolver: "#{@userIdKeyResolver}"  # por usuário (email)
            - StripPrefix=1

  redis:
    host: redis-cluster.example.com
    port: 6379
    password: ${REDIS_PASSWORD}
    timeout: 2000ms
    lettuce:
      pool:
        max-active: 10
        max-idle: 5

management:
  prometheus:
    metrics:
      export:
        enabled: true
```

```java
// Key resolver — determina o "cliente" para rate limiting
@Configuration
public class RateLimiterConfig {

    @Bean
    public KeyResolver ipAddressKeyResolver() {
        return exchange -> Mono.just(
            exchange.getRequest().getRemoteAddress().getAddress().getHostAddress()
        );
    }

    @Bean
    public KeyResolver userIdKeyResolver() {
        return exchange -> {
            // Extrai o email do corpo da requisição (login)
            String email = extractEmailFromBody(exchange);
            return Mono.just("login:" + (email != null ? email : "anonymous"));
        };
    }

    private String extractEmailFromBody(ServerWebExchange exchange) {
        // Implementação para extrair email do JSON body
        try {
            var body = exchange.getRequest().getBody();
            // JSON parsing (usar ObjectMapper ou similar)
            return "email_extraido";
        } catch (Exception e) {
            return null;
        }
    }
}
```

### Teste de Rate Limiting — MockMvc com exceção 429

```java
// Test — validar que rate limit retorna HTTP 429
@SpringBootTest
@AutoConfigureMockMvc
public class RateLimiterTest {

    @Autowired private MockMvc mockMvc;

    @Test
    public void deveRetornarHttp429QuandoExcederRateLimit() throws Exception {
        // Limite configurado: 3 requisições por minuto para /api/auth/login

        for (int i = 0; i < 3; i++) {
            mockMvc.perform(post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"email\":\"test@example.com\", \"senha\":\"pass\"}")
            ).andExpect(status().isOk());  // Primeiras 3 passam
        }

        // 4ª requisição deve ser bloqueada
        mockMvc.perform(post("/api/auth/login")
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"email\":\"test@example.com\", \"senha\":\"pass\"}")
        ).andExpect(status().isTooManyRequests())  // HTTP 429
         .andExpect(header().exists("Retry-After"))
         .andExpect(content().string(containsString("limite de requisições")));
    }

    @Test
    public void devePermitirRequisicaoAposTimeoutDoRateLimit() throws Exception {
        // Enche o rate limit
        for (int i = 0; i < 3; i++) {
            mockMvc.perform(post("/api/auth/login")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"email\":\"test@example.com\", \"senha\":\"pass\"}")
            ).andExpect(status().isOk());
        }

        // Aguarda reset (1 segundo)
        Thread.sleep(1100);

        // Próxima requisição passa
        mockMvc.perform(post("/api/auth/login")
            .contentType(MediaType.APPLICATION_JSON)
            .content("{\"email\":\"test@example.com\", \"senha\":\"pass\"}")
        ).andExpect(status().isOk());
    }
}
```

**Checklist CORS + Rate Limiting:**
- ✅ `allowedOrigins` é whitelist explícita (nunca `*`)
- ✅ `allowedMethods` é lista branca (GET, POST, PUT, DELETE — sem `*`)
- ✅ `allowCredentials = true` apenas se necessário
- ✅ `maxAge` é configurado (3600s padrão — ajustar conforme workload)
- ✅ Rate limiter aplicado a endpoints públicos e críticos
- ✅ Fallback method retorna HTTP 429 com `Retry-After` header
- ✅ Rate limit é centralizado em Redis para sistemas distribuídos
- ✅ Métricas do Prometheus estão exportadas: `resilience4j_ratelimiter_calls_total`
- ✅ Alerta configurado: taxa de 429 > 5% em 10min (possível ataque DDoS)



```python
# Python — FastAPI com dependência de autenticação
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def get_current_user(token: str = Depends(security)):
    payload = verify_jwt(token.credentials)
    if not payload:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
    return payload

@app.get("/api/pedidos/{pedido_id}")
async def get_pedido(pedido_id: int, user=Depends(get_current_user)):
    pedido = await repo.buscar(pedido_id)
    if pedido.usuario_id != user["sub"]:  # ownership check
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
    return pedido
```

