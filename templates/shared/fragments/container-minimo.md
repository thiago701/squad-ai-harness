## Container mínimo
Multi-stage build; imagem final mínima (distroless/alpine/scratch conforme runtime); usuário não-root; sem toolchain na imagem final; healthcheck declarado; variáveis de ambiente para config (12-factor). Tag imutável por digest em produção.
