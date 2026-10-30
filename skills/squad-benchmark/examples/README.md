# Exemplo populado (v1–v4)

Dashboard de exemplo gerado pela skill `squad-benchmark` com dados fictícios
parecidos com o esboço do caderno (evolução v1 → v4). Serve para validar o
visual sem precisar registrar marcos.

- `dashboard.exemplo.html` — abra offline no navegador (Chart.js via CDN).
- `benchmark.exemplo.csv` — export correspondente.

Para gerar o seu próprio (no HOME do usuário, `~/.squad-ai/benchmark/`):

```bash
python3 ../scripts/registrar.py --versao v1 --contexto "baseline" \
  --A 60 --B 40 --C 70 --D 2.5x --E 55
python3 ../scripts/dashboard.py render
```

> Estes arquivos são **snapshots ilustrativos**; o banco real e o dashboard
> vivo ficam em `~/.squad-ai/benchmark/`, fora do repositório.
