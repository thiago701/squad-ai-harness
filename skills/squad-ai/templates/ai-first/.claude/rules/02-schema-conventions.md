# Rule 02 — Convenções de schema (padrão corporativo)

Aplica-se a: todo arquivo `*.dbml`, `*.sql` em `db/migration/**` e qualquer
`@Entity` JPA em `infra/persistence/**`.

## Regra

Toda tabela persistente **obriga**:

1. **Primary Key** `codigo_identificacao_<entidade>` `UUID` com `gen_random_uuid()`.
2. **Foreign Keys** `codigo_identificacao_<entidade_referenciada>` — nunca `fk_*` ou `id_*`.
3. **Seis colunas de auditoria** obrigatórias:
   - `usuario_criacao_registro` · `data_hora_criacao_registro`
   - `usuario_atualizacao_registro` · `data_hora_atualizacao_registro`
   - `data_hora_exclusao_registro` · `usuario_exclusao_registro`
4. **Soft delete** via `data_hora_exclusao_registro IS NULL`.
   Queries de leitura **jamais** retornam registros excluídos.
5. **Optimistic lock** via `numero_versao_registro BIGINT` (mapeado `@Version`).
6. **Timestamps** sempre `TIMESTAMPTZ` (UTC).
7. **Nomes** em snake_case, português, substantivos completos.

## Mapeamento JPA padrão

```java
@Entity
@Table(name = "<entidade>", schema = "<contexto>")
@EntityListeners(AuditingEntityListener.class)
public class <Entidade>Entity {

    @Id
    @Column(name = "codigo_identificacao_<entidade>")
    private UUID codigoIdentificacao<Entidade>;

    @CreatedBy  @Column(name = "usuario_criacao_registro", updatable = false)
    private String usuarioCriacaoRegistro;

    @CreatedDate @Column(name = "data_hora_criacao_registro", updatable = false)
    private Instant dataHoraCriacaoRegistro;

    @LastModifiedBy @Column(name = "usuario_atualizacao_registro")
    private String usuarioAtualizacaoRegistro;

    @LastModifiedDate @Column(name = "data_hora_atualizacao_registro")
    private Instant dataHoraAtualizacaoRegistro;

    @Column(name = "data_hora_exclusao_registro")
    private Instant dataHoraExclusaoRegistro;

    @Column(name = "usuario_exclusao_registro")
    private String usuarioExclusaoRegistro;

    @Version @Column(name = "numero_versao_registro")
    private Long numeroVersaoRegistro;
}
```

## Rejeição automática em code review

Qualquer PR que introduza:

- Coluna de ID com nome diferente de `codigo_identificacao_*`.
- FK com nome `fk_*`, `id_*` ou afim.
- Tabela sem as 6 colunas de auditoria.
- `DELETE FROM` (hard delete) em código de produção.
- Timestamps sem `TIMESTAMPTZ`.
- Pessimistic lock onde optimistic lock resolve.

...é **rejeitado imediatamente**. Não é negociação.
