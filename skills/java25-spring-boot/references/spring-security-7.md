# Spring Security 7 — Guia Rápido

## O que Mudou

Spring Security 7 (incluído no Spring Boot 4) traz:
- Null-safety com JSpecify em toda a API
- Modularização mais fina dos JARs
- Remoção de APIs deprecated desde a versão 6.x
- Melhor integração com virtual threads (sem ThreadLocal leaks)
- OAuth2 Resource Server com melhor suporte a múltiplos issuers

## Configuração Padrão Recomendada

### API REST com JWT (OAuth2 Resource Server)

```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {

    @Bean
    SecurityFilterChain apiFilterChain(HttpSecurity http) throws Exception {
        http
            .securityMatcher("/api/**")
            .csrf(csrf -> csrf.disable())  // APIs stateless não precisam de CSRF
            .sessionManagement(session ->
                session.sessionCreationPolicy(SessionCreationPolicy.STATELESS))
            .authorizeHttpRequests(auth -> auth
                .requestMatchers("/api/public/**").permitAll()
                .requestMatchers("/api/admin/**").hasRole("ADMIN")
                .requestMatchers(HttpMethod.GET, "/api/products/**").permitAll()
                .anyRequest().authenticated()
            )
            .oauth2ResourceServer(oauth2 -> oauth2
                .jwt(jwt -> jwt.jwtAuthenticationConverter(jwtConverter()))
            );

        return http.build();
    }

    @Bean
    JwtAuthenticationConverter jwtConverter() {
        var converter = new JwtAuthenticationConverter();
        var grantedAuthoritiesConverter = new JwtGrantedAuthoritiesConverter();
        grantedAuthoritiesConverter.setAuthorityPrefix("ROLE_");
        grantedAuthoritiesConverter.setAuthoritiesClaimName("roles");
        converter.setJwtGrantedAuthoritiesConverter(grantedAuthoritiesConverter);
        return converter;
    }
}
```

```properties
# application.properties
spring.security.oauth2.resourceserver.jwt.issuer-uri=https://auth.myapp.com
spring.security.oauth2.resourceserver.jwt.audiences=my-api
```

### Múltiplos Issuers (Multi-tenant)

```java
@Bean
JwtDecoder jwtDecoder() {
    var issuer1 = JwtDecoders.fromIssuerLocation("https://auth-tenant1.com");
    var issuer2 = JwtDecoders.fromIssuerLocation("https://auth-tenant2.com");

    return token -> {
        // Determina issuer do token e delega para o decoder correto
        var claims = JWTParser.parse(token).getJWTClaimsSet();
        return switch (claims.getIssuer()) {
            case "https://auth-tenant1.com" -> issuer1.decode(token);
            case "https://auth-tenant2.com" -> issuer2.decode(token);
            default -> throw new JwtException("Unknown issuer");
        };
    };
}
```

## Method Security com Anotações

```java
@Service
public class OrderService {

    @PreAuthorize("hasRole('USER') and #userId == authentication.principal.claims['sub']")
    public List<Order> findByUser(String userId) {
        return orderRepository.findByUserId(userId);
    }

    @PreAuthorize("hasRole('ADMIN')")
    @PostFilter("filterObject.status != 'DELETED'")
    public List<Order> findAll() {
        return orderRepository.findAll();
    }

    @PreAuthorize("@orderSecurity.canCancel(#orderId, authentication)")
    public void cancelOrder(Long orderId) {
        // Custom security logic delegada para bean
    }
}

@Component
public class OrderSecurity {
    public boolean canCancel(Long orderId, Authentication auth) {
        var order = orderRepository.findById(orderId).orElseThrow();
        return order.userId().equals(auth.getName()) || isAdmin(auth);
    }
}
```

## Integração com Scoped Values

```java
// Padrão: propagar contexto de segurança via ScopedValue em virtual threads
static final ScopedValue<SecurityContext> SECURITY_CTX = ScopedValue.newInstance();

@Bean
SecurityFilterChain filterChain(HttpSecurity http) throws Exception {
    http.addFilterBefore(new ScopedValueSecurityFilter(), UsernamePasswordAuthenticationFilter.class);
    return http.build();
}

// Filter que propaga o SecurityContext via ScopedValue
public class ScopedValueSecurityFilter extends OncePerRequestFilter {
    @Override
    protected void doFilterInternal(HttpServletRequest request,
                                     HttpServletResponse response,
                                     FilterChain chain) throws ServletException, IOException {
        var ctx = SecurityContextHolder.getContext();
        ScopedValue.where(SECURITY_CTX, ctx).run(() -> {
            try { chain.doFilter(request, response); }
            catch (Exception e) { throw new RuntimeException(e); }
        });
    }
}
```

## Testes de Segurança

```java
@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
class SecurityIntegrationTest {

    @Autowired
    RestTestClient client;

    @Test
    void publicEndpointShouldBeAccessible() {
        client.get().uri("/api/public/health")
            .exchange()
            .expectStatus().isOk();
    }

    @Test
    void protectedEndpointShouldReturn401() {
        client.get().uri("/api/orders")
            .exchange()
            .expectStatus().isUnauthorized();
    }

    @Test
    @WithMockUser(roles = "ADMIN")
    void adminEndpointShouldBeAccessibleByAdmin() {
        client.get().uri("/api/admin/users")
            .exchange()
            .expectStatus().isOk();
    }

    @Test
    void shouldAcceptValidJwt() {
        client.get().uri("/api/orders")
            .headers(h -> h.setBearerAuth(generateValidJwt()))
            .exchange()
            .expectStatus().isOk();
    }
}
```
