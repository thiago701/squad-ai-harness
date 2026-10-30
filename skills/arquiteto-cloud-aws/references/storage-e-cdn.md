# Referência — Storage e CDN (S3, CloudFront)

> Parte da skill `arquiteto-cloud-aws`. Carregue este arquivo sob demanda quando a tarefa tocar este eixo. Hub: `../SKILL.md`.
### Storage — S3

```
Free tier S3: 5GB + 20.000 GET + 2.000 PUT por 12 meses
Após free tier: $0.023/GB/mês (um dos mais baratos do mercado)

S3 resolve sem código:
  ✓ Upload direto do browser (Presigned URLs — zero tráfego pelo servidor)
  ✓ Hospedagem de site estático (React/Angular sem servidor)
  ✓ Backup e arquivamento com lifecycle automático
  ✓ Data lake para analytics com Athena
  ✓ Distribuição via CloudFront (CDN global)
```

```python
# Python — Presigned URL para upload direto do cliente ao S3
# O arquivo vai direto browser → S3, sem passar pelo servidor da aplicação
import boto3
from dataclasses import dataclass

s3 = boto3.client("s3")

@dataclass
class PresignedUpload:
    url: str
    fields: dict
    s3_key: str

def gerar_url_upload(bucket: str, user_id: str, nome_arquivo: str,
                     content_type: str = "image/jpeg",
                     tamanho_max_mb: int = 10) -> PresignedUpload:
    s3_key = f"uploads/{user_id}/{uuid.uuid4()}/{nome_arquivo}"

    response = s3.generate_presigned_post(
        Bucket=bucket,
        Key=s3_key,
        Fields={"Content-Type": content_type},
        Conditions=[
            {"Content-Type": content_type},
            ["content-length-range", 1, tamanho_max_mb * 1024 * 1024],
        ],
        ExpiresIn=300,  # URL válida por 5 minutos
    )
    return PresignedUpload(url=response["url"], fields=response["fields"], s3_key=s3_key)

# No frontend: POST multipart para response.url com response.fields
# Resultado: zero custo de compute para upload de arquivos
```

---

### CloudFront — CDN Global + Cache Invalidation

**Free tier CloudFront:**
- 1TB de dados egress/mês **permanente** (não expira após 12 meses)
- 10 milhões de requisições/mês permanente
- Após free tier: $0.085/GB (um dos CDNs mais baratos)

```
CloudFront resolve:
  ✓ Distribuição global (edge nodes em 500+ locais)
  ✓ Cache automático com TTL configurável
  ✓ HTTPS/TLS gratuito via ACM
  ✓ Integração com S3, ALB, API Gateway, custom origins
  ✓ Query string e cookie forwarding para cache inteligente
  ✓ Path-based routing (diferentes behaviors para /api vs /static)
```

#### Cache Behavior Configuration

**TTL defaults — balancear entre freshness e hit rate:**

```yaml
# Exemplo: React SPA + API dinâmica
CloudFront distribution:
  default-behavior:
    # Cache estático (JS/CSS/imagens)
    path-pattern: "/static/*"
    ttl:
      minTTL: 0
      defaultTTL: 86400       # 24h
      maxTTL: 31536000        # 365 dias (versioning via ?v=hash)
    forward-cookies: false
    forward-query-strings: false

  api-behavior:
    # API dinâmica — cache curto ou zero
    path-pattern: "/api/*"
    ttl:
      minTTL: 0
      defaultTTL: 0           # Zero cache (fresh sempre)
      maxTTL: 300             # Fallback 5 min se origin down
    forward-cookies: true     # Session cookies
    forward-query-strings: true
    allowed-methods: ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
```

#### Cache Invalidation Strategy

**Custo:**
- Primeiras 1.000 paths/mês: **grátis**
- Acima de 1.000: **$0.005 por path** (R$0.025/caminho)
- Invalidação via `/*` conta como 1 path (não multiplicativo)

**Regra de ouro:**
```
Preferir VERSIONING sobre INVALIDATION:
  ✓ /static/app.js?v=hash     → sempre 365 dias de cache
  ✗ /static/app.js            → invalida toda vez (custo)

Benefício: sem custo, sem latência de espera de purge
```

**Quando INVALIDAR (justificado):**
```
  1. Deploy de app estática → invalidar /* (conta como 1 path, grátis se < 1000/mês)
  2. Hotfix urgente → invalidar /página-específica.html
  3. Content update → invalidar /blog/* se blog estiver não-versionado

Nunca invalidar:
  × A cada commit (versione em vez disso)
  × Assets estáticos (use query string ?v=hash)
  × Páginas que não mudam (deixe TTL fazer seu job)
```

#### Invalidation via CDK / CLI

```java
// Java — CDK com automatização de invalidation
@Component
public class CloudFrontInvalidationHandler {

    private final CloudFrontClient cf;

    public void invalidateOnDeploy(String distributionId, List<String> paths) {
        var request = CreateInvalidationRequest.builder()
            .distributionId(distributionId)
            .invalidationBatch(InvalidationBatch.builder()
                .paths(Paths.builder()
                    .quantity(paths.size())
                    .items(paths)
                    .build())
                .callerReference(UUID.randomUUID().toString())
                .build())
            .build();

        var response = cf.createInvalidation(request);
        logger.info("Invalidation ID: {}", response.invalidation().id());
        // Retornar ID para CI/CD monitorar status
    }
}

// Exemplo — invalida apenas na falha de health check
@Component
public class HealthCheckInvalidation {

    public void invalidateIfHealthFails(String distributionId) {
        // Check origin health
        if (!isOriginHealthy()) {
            // Invalida cache stale (força refetch origin)
            invalidateOnDeploy(distributionId, List.of("/index.html", "/*"));
        }
    }
}
```

```bash
# AWS CLI — invalidar paths específicos
aws cloudfront create-invalidation \
  --distribution-id E123EXAMPLE \
  --paths "/index.html" "/api/v1/config"

# Ou tudo (conta como 1 path)
aws cloudfront create-invalidation \
  --distribution-id E123EXAMPLE \
  --paths "/*"

# Verificar status
aws cloudfront get-invalidation --distribution-id E123EXAMPLE --id I123
```

#### Query String & Cookie Forwarding

```yaml
# Configurar CloudFront para cache inteligente
cache-behaviors:
  - path-pattern: "/pedidos/*"
    forward-query-strings: true    # Cache separado por ?sort=price&limit=10
    forward-cookies:
      forward-list: ["session_id"]  # Session cookie → sem cache
      # Sem session → cache 1h
    cache-key-builder:
      headers: ["Accept-Language", "Accept-Encoding"]
```

**Impacto na taxa de acerto (cache hit rate):**
```
100% forwarding (todas queries + cookies) → 20–30% hit rate
Selective (apenas necessário) → 70–85% hit rate
Nenhum forwarding (versionado) → 95%+ hit rate
```

#### Behavior Rules & Path Routing

```java
// Java CDK — múltiplos behaviors
var dist = CloudFrontDistribution.Builder.create(this, "Dist")
    .defaultBehavior(BehaviorOptions.builder()
        .origin(s3Origin)
        .viewerProtocolPolicy(ViewerProtocolPolicy.REDIRECT_TO_HTTPS)
        .cachePolicy(CachePolicy.CACHING_OPTIMIZED)
        .build())
    .additionalBehaviors(Map.of(
        "/api/*",
        BehaviorOptions.builder()
            .origin(apiOrigin)
            .viewerProtocolPolicy(ViewerProtocolPolicy.HTTPS_ONLY)
            .cachePolicy(CachePolicy.CACHING_DISABLED)  // API sempre fresh
            .build(),
        "/static/*",
        BehaviorOptions.builder()
            .origin(s3Origin)
            .cachePolicy(CachePolicy.CACHING_OPTIMIZED_FOR_STATIC)
            .edgeCompression(true)
            .build()
    ))
    .build();
```

#### CloudFront Cache Invalidation Checklist

```
□ TTL strategy definida (static vs dynamic vs api)
□ Versioning implementado para assets (query string ou filename hash)
□ Query string forwarding apenas se necessário (reduz hit rate)
□ Cookie forwarding restrito (session_id, auth, nunca tracking)
□ Path-based behaviors configurados (/api → zero cache, /static → 365 dias)
□ WAF associado para proteção DDoS
□ Logging habilitado em S3 (audit trail)
□ Custom domain com certificado ACM (HTTPS obrigatório)
□ Gzip compression habilitado para text/* e application/json
□ Origin health checks configurados (falha → fallback 5min TTL)
□ Monitoring: cache hit rate > 85% para static assets
```

---

## S3 — Especialista Enterprise

> S3 não é "só armazenar arquivos". Em Tier 0, S3 é storage de mídia, data lake, audit log, queue de jobs, e CDN origin. Domine cada classe e padrão.

### Storage Classes — Quando Usar Cada Uma

| Classe | Caso de uso | $/GB/mês | Retrieval | Min duration |
|--------|-------------|----------|-----------|--------------|
| **Standard** | Hot data, < 30 dias, alta freq | $0.023 | Imediato | — |
| **Intelligent-Tiering** | Acesso variável/desconhecido | $0.023 + monitoring | Imediato | — |
| **Standard-IA** | Cold mas precisa imediato | $0.0125 | Imediato | 30 dias |
| **One Zone-IA** | Cold + replicável (cache) | $0.01 | Imediato | 30 dias |
| **Glacier Instant Retrieval** | Archive imediato | $0.004 | Imediato | 90 dias |
| **Glacier Flexible Retrieval** | Archive 1-12h | $0.0036 | 1-12h | 90 dias |
| **Glacier Deep Archive** | Archive 12h+ | $0.00099 | 12h+ | 180 dias |
| **S3 Express One Zone** | Sub-10ms latency, ML/analytics | $0.16 | < 10ms | — |

**Erro comum #1:** Standard-IA para arquivos < 30 dias → cobra mínimo 30 dias mesmo se deletar.
**Erro comum #2:** Object < 128KB em IA → cobra mínimo 128KB.

**Regra de ouro enterprise:** habilite **Intelligent-Tiering** como default em buckets de mídia/uploads. Custo de monitoring ($0.0025/1000 objetos) é desprezível vs economia automática.

### S3 Express One Zone — Sub-10ms Latency

Lançado em 2023 para workloads ML/analytics/cache que precisam latência sub-10ms (vs 100-200ms do S3 Standard).

```java
CfnDirectoryBucket expressBucket = CfnDirectoryBucket.Builder.create(this, "ExpressBucket")
    .bucketName("orders-express--use1-az4--x-s3")     // sufixo --azX--x-s3 obrigatório
    .dataRedundancy("SingleAvailabilityZone")
    .locationName("use1-az4")
    .build();
```

**10x mais rápido**, **8x mais caro** ($0.16/GB vs $0.023). Use só para hotpath: cache de embeddings, feature store, intermediate analytics.

### Multipart Upload para Arquivos Grandes

**Regra:** arquivos > 100 MB **devem** usar multipart upload (paralelizável, retry por parte, mais rápido).

```java
S3TransferManager transferManager = S3TransferManager.builder()
    .s3Client(S3AsyncClient.crtBuilder()                  // CRT client = throughput 10x maior
        .region(Region.US_EAST_1)
        .targetThroughputInGbps(10.0)                     // 10 Gbps target
        .minimumPartSizeInBytes(8L * 1024 * 1024)         // 8 MB chunks
        .build())
    .build();

UploadFileRequest req = UploadFileRequest.builder()
    .putObjectRequest(b -> b.bucket("media-prod").key("video.mp4")
        .storageClass(StorageClass.INTELLIGENT_TIERING)
        .serverSideEncryption(ServerSideEncryption.AWS_KMS)
        .ssekmsKeyId(kmsKeyArn)
        .metadata(Map.of("correlation-id", correlationId)))
    .source(Paths.get("/local/video.mp4"))
    .addTransferListener(LoggingTransferListener.create())
    .build();

FileUpload upload = transferManager.uploadFile(req);
upload.completionFuture().join();
```

**S3 CRT client (Java SDK v2)** é o cliente AWS Common Runtime — multi-threaded, network-optimized, suporta multipart automático, paralelismo nativo. **10x throughput** vs cliente Java padrão para arquivos grandes. Use para qualquer workload que move > 100 MB/req.

### Transfer Acceleration

Para uploads de clientes geograficamente distribuídos (mobile users globais):

```java
bucket.addToResourcePolicy(...);
CfnBucket cfnBucket = (CfnBucket) bucket.getNode().getDefaultChild();
cfnBucket.setAccelerateConfiguration(CfnBucket.AccelerateConfigurationProperty.builder()
    .accelerationStatus("Enabled")
    .build());
```

**Endpoint:** `bucket.s3-accelerate.amazonaws.com` — usa rede edge da CloudFront. **Cobra extra ($0.04/GB)** mas dobra throughput em uploads transcontinentais.

### Multi-Region Access Points

Para apps globais que precisam leitura/escrita em qualquer região:

```java
CfnMultiRegionAccessPoint mrap = CfnMultiRegionAccessPoint.Builder.create(this, "Mrap")
    .name("orders-global")
    .regions(List.of(
        CfnMultiRegionAccessPoint.RegionProperty.builder().bucket("orders-us-east-1").build(),
        CfnMultiRegionAccessPoint.RegionProperty.builder().bucket("orders-eu-west-1").build(),
        CfnMultiRegionAccessPoint.RegionProperty.builder().bucket("orders-ap-southeast-1").build()
    ))
    .publicAccessBlockConfiguration(...)
    .build();
```

App acessa endpoint único `mrap-orders-global.accesspoint.s3-global.amazonaws.com`, AWS roteia para a região mais próxima automaticamente. **Failover automático** se uma região cair.

### Cross-Region Replication (CRR) — DR

```java
bucket.addCrossRegionReplication(BucketReplicationProps.builder()
    .destinationBucket(drBucket)              // bucket em outra região
    .replicationTimeControl(true)             // RTC: SLA 15 min p99
    .metrics(true)
    .deleteMarkerReplication(true)
    .priority(1)
    .build());
```

**Replication Time Control (RTC):** garante 99.99% dos objetos replicados em < 15 min. Custo extra mas obrigatório para DR de Tier 0.

### Encryption — Bucket Key (90% redução de custo KMS)

```java
Bucket bucket = Bucket.Builder.create(this, "EncBucket")
    .encryption(BucketEncryption.KMS)
    .bucketKeyEnabled(true)                  // ⭐ reduz chamadas KMS em 99%
    .encryptionKey(kmsKey)
    .build();
```

**Sem bucket key:** cada PUT/GET chama KMS (custo $0.03/10K requests).
**Com bucket key:** S3 cacheia uma chave intermediária por bucket → 1 chamada KMS por hora vs 1 por request. Para um bucket com 1B requests/mês, **economiza ~$3.000/mês**.

### Presigned URLs com Limites

```java
S3Presigner presigner = S3Presigner.create();

PresignedPutObjectRequest presignedPut = presigner.presignPutObject(
    PutObjectPresignRequest.builder()
        .signatureDuration(Duration.ofMinutes(5))     // expira em 5 min
        .putObjectRequest(p -> p
            .bucket("uploads")
            .key("user/" + userId + "/" + uuid)
            .contentLengthRange(1, 50 * 1024 * 1024)  // entre 1B e 50 MB
            .contentType("image/jpeg")
            .metadata(Map.of("user-id", userId)))
        .build());

return presignedPut.url().toString();
```

**Frontend faz upload direto para S3** — sem passar pelo backend. Economiza compute, network e elimina backend como bottleneck. Padrão em apps mobile.

### S3 Object Lambda — Transformação on-the-fly

Aplica transformação (resize, filter, redact PII) sem duplicar dados:

```java
CfnAccessPoint ap = CfnAccessPoint.Builder.create(this, "BaseAp")
    .bucket("originals")
    .name("originals-ap")
    .build();

CfnAccessPoint olap = CfnAccessPoint.Builder.create(this, "ResizeOlap")
    .bucket("dummy")    // ignored
    .name("originals-resize")
    .build();
```

App acessa `s3://originals-resize/photo.jpg?w=400` → invoca Lambda → Lambda lê original, redimensiona, retorna. Zero storage extra.

### Lifecycle Policies — Otimização Automática

```java
bucket.addLifecycleRule(LifecycleRule.builder()
    .id("archive-old-uploads")
    .enabled(true)
    .prefix("uploads/")
    .transitions(List.of(
        Transition.builder()
            .storageClass(StorageClass.INTELLIGENT_TIERING).transitionAfter(Duration.days(0))
            .build(),
        Transition.builder()
            .storageClass(StorageClass.GLACIER_INSTANT_RETRIEVAL).transitionAfter(Duration.days(90))
            .build(),
        Transition.builder()
            .storageClass(StorageClass.DEEP_ARCHIVE).transitionAfter(Duration.days(365))
            .build()
    ))
    .expiration(Duration.days(2555))         // 7 anos (compliance)
    .abortIncompleteMultipartUploadAfter(Duration.days(7))  // CRÍTICO: lixo de uploads incompletos
    .build());
```

**Sempre habilitar `abortIncompleteMultipartUploadAfter`** — multipart uploads incompletos cobram storage indefinidamente.

### Métricas e Alarmes

```java
Metric requestsMetric = Metric.Builder.create()
    .namespace("AWS/S3")
    .metricName("AllRequests")
    .dimensionsMap(Map.of("BucketName", bucket.getBucketName(), "FilterId", "EntireBucket"))
    .statistic("Sum")
    .period(Duration.minutes(5))
    .build();

new Alarm(this, "HighErrorRate", AlarmProps.builder()
    .metric(new Metric.Builder()
        .namespace("AWS/S3")
        .metricName("4xxErrors")
        .dimensionsMap(Map.of("BucketName", bucket.getBucketName(), "FilterId", "EntireBucket"))
        .build())
    .threshold(100)
    .evaluationPeriods(3)
    .build());
```

**Habilitar Storage Class Analysis e Storage Lens** para visibilidade FinOps em dashboards.

---

