# python-memoria · reference — Dados: pandas, polars, numpy, arrow, DuckDB

> Hub: `../SKILL.md`. Regras: MEM-08, 09, 10 (+ leitura MEM-20). Princípio: **tipo declarado + pedaços +
> formato colunar**. DataFrame "default" é a forma mais cara de guardar um CSV em memória.

## 1. pandas — o que muda o pico (MEM-08/09/10)

```python
# ANTES — tudo object/float64, tudo em memória, uma Series por linha
df = pd.read_csv("pedidos.csv")
for _, r in df.iterrows(): validar(r)
saida = pd.DataFrame()
for parte in partes: saida = pd.concat([saida, parte])        # quadrático

# DEPOIS
dtypes = {"id": "string", "status": "category", "valor_centavos": "int32", "cliente_id": "string"}
pedacos = []
for chunk in pd.read_csv("pedidos.csv", usecols=list(dtypes), dtype=dtypes, chunksize=200_000):
    chunk = chunk[chunk["valor_centavos"] > 0]                 # vetorizado; nada de iterrows
    pedacos.append(agregar(chunk))                             # reduz antes de guardar
saida = pd.concat(pedacos, ignore_index=True)                  # UMA vez
```

- **Meça**: `df.memory_usage(deep=True).sum()` (sem `deep` strings mentem) e `df.info(memory_usage="deep")`.
- **dtypes**: `category` para baixa cardinalidade (status, UF) — de 8+ bytes/objeto para 1-2 bytes/código;
  inteiros/floats menores (`int32`, `float32`, `pd.to_numeric(downcast=…)`); `string[pyarrow]` ou
  `dtype_backend="pyarrow"` (pandas ≥ 2.0) para texto e nulos sem `object`; datas parseadas com `parse_dates`.
- **`usecols`** corta colunas na leitura; **`chunksize`/`iterator`** faz streaming; **`nrows`** para explorar.
- **`engine="pyarrow"`** em `read_csv` (multithread, menos cópias) quando a coluna de tipos permite.
- **Números do guia oficial** (1,05 M linhas): `category` numa coluna de texto 13,7 MB → 1,05 MB; `to_numeric(downcast=)`
  int64 → uint16 8,4 MB → 2,1 MB; total do DataFrame 47,3 MB → 20,0 MB (**0,42×**); `read_parquet(columns=[...])`
  ≈ **1/10** da memória do arquivo de 40 colunas. Strings: 1 M de ~18 chars em `object` 75 MB vs `string[pyarrow]`
  22 MB (**−70 %**; o ganho encolhe em strings longas).
- **pandas 3.0 (01/2026)**: **Copy-on-Write é o padrão** (PDEP-7) — resultados se comportam como cópias, cópia real só
  quando necessário, `SettingWithCopyWarning` sumiu e `pd.options.mode.copy_on_write` não tem mais efeito; o dtype
  **`str` padrão é apoiado em PyArrow** (PDEP-14) no lugar de `object`; exige Python ≥ 3.11. Em 2.x, ligue
  `pd.options.mode.copy_on_write = True` para antecipar; `.copy()` explícito só quando vai mutar e precisa do original.
- **Evite**: `iterrows` (MEM-09), `apply(axis=1)` com lambda Python, `concat` em loop (MEM-10), `df.values`
  em DataFrame heterogêneo (vira `object`), `inplace=True` como "economia" (não economiza).
- **Agregue cedo**: `groupby(...).agg(...)` por chunk e depois combine; nunca guarde o bruto para agregar no fim.

## 2. polars — lazy por padrão para ETL grande

```python
import polars as pl
plano = (pl.scan_csv("pedidos.csv", dtypes={"status": pl.Categorical, "valor_centavos": pl.Int32})
           .filter(pl.col("valor_centavos") > 0)
           .group_by("cliente_id").agg(pl.col("valor_centavos").sum()))
plano.sink_parquet("saida.parquet")          # streaming: nunca materializa o CSV inteiro
# ou: plano.collect(engine="streaming")      # novo engine (≥ 1.31); `collect(streaming=True)` foi REMOVIDO em 1.31
# saída particionada por tamanho: plano.sink_parquet(pl.PartitionMaxSize("saida_{part}.parquet", max_size=5_000_000))
```
`scan_*` constrói um plano; o otimizador empurra filtros/projeções para a leitura; `sink_*` grava em
streaming. **Polars 2.0 (RC 09/2026) faz do streaming o engine padrão** (`engine="auto"`; volte com
`pl.Config.set_engine_affinity("in-memory")`). Limite real: `group_by`/`join` por igualdade/`sort` ainda precisam
que a tabela hash caiba em RAM — out-of-core desses operadores não está concluído; `.show_graph(engine="streaming",
plan_stage="physical")` mostra o que vai rodar em pedaços. Converta para pandas só na borda
(`.to_pandas(use_pyarrow_extension_array=True)`).

## 3. numpy — views, dtypes, memmap

- Fatia básica, `reshape` (quando possível), `.T` e `ravel()` são **views** (sem cópia); `arr.copy()`, `flatten()`,
  operações com `dtype` misto e *fancy indexing* copiam — `arr.base is None`/`np.shares_memory(a, b)` confirmam.
  O reverso também importa: uma view **pequena** guardada em estrutura longa mantém o array **inteiro** vivo —
  `pequena = grande[a:b].copy()` quando o grande deve morrer.
- `float64` → `float32` corta pela metade; inteiros no menor `dtype` que cabe; `bool` em vez de `int8` de 0/1.
- `np.memmap("grande.npy", dtype=…, mode="r")` para arquivos maiores que a RAM; `np.load(..., mmap_mode="r")`.
- Operações **in-place** (`np.add(a, b, out=a)`, `a *= 2`) evitam temporários; expressões longas criam vários.
- Lista de números Python → `array.array("i")`/numpy: 28 bytes por `int` + 8 do ponteiro vs 4-8 bytes.

## 4. Arrow / parquet / DuckDB

- **Parquet, não CSV**: colunar, comprimido, tipado, leitura por coluna/row group; `pq.ParquetFile(f).iter_batches()`
  para streaming; `columns=[...]` em `read_parquet`.
- Arrow mantém **buffers imutáveis zero-copy** entre pandas (`dtype_backend="pyarrow"`), polars, DuckDB;
  `pa.total_allocated_bytes()` mostra o que o pool do Arrow segura; `pa.memory_map` para IPC/Feather.
- **DuckDB** executa SQL direto sobre parquet/CSV com *spill to disk*: ETL que não cabe em RAM sem pandas
  (`duckdb.sql("select … from 'pedidos/*.parquet'").write_parquet(...)`). Resultado grande → `fetch_record_batch`.
  Em container, declare o teto: o `memory_limit` padrão é **80 % da RAM da máquina** (não do cgroup) —
  `SET memory_limit='4GB'` (≤ limite do container − folga) e `temp_directory` em disco gravável; agregações com
  muitos grupos, `DISTINCT`, joins maiores que a RAM, sort e window já fazem spill sem configuração extra.

## 5. Checklist de dados (review P2.MEM)

- [ ] `read_*` com `usecols` + `dtype`/`dtype_backend`; streaming (`chunksize`/`scan_*`/`iter_batches`) quando o dado pode crescer (MEM-08).
- [ ] Sem `iterrows`/`apply(axis=1)` em caminho quente (MEM-09); `concat` uma vez (MEM-10).
- [ ] `category`/inteiros curtos/`float32` onde a precisão permite; strings em arrow.
- [ ] Agregação por pedaço antes de reter; parquet como formato intermediário; DuckDB/polars para o que não cabe.
- [ ] `memory_usage(deep=True)` antes/depois registrado no PR; teste de orçamento no job.

## Fontes

- pandas — Scaling to large datasets: https://pandas.pydata.org/docs/user_guide/scale.html · `read_csv`: https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html · Copy-on-Write: https://pandas.pydata.org/docs/user_guide/copy_on_write.html · PyArrow backend: https://pandas.pydata.org/docs/user_guide/pyarrow.html · `memory_usage`: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.memory_usage.html
- pandas 3.0 — What's New (CoW padrão, dtype `str` Arrow): https://pandas.pydata.org/docs/whatsnew/v3.0.0.html · pythonspeed — strings `object` vs `string[pyarrow]`: https://pythonspeed.com/articles/pandas-string-dtype-memory/ · `memory_usage(deep=True)` é estimativa: https://pythonspeed.com/articles/pandas-dataframe-series-memory-usage/
- polars — Lazy API: https://docs.pola.rs/user-guide/lazy/ · execução/streaming (`engine="streaming"`, `sink_*`): https://docs.pola.rs/user-guide/lazy/execution/ · remoção de `streaming=True` (1.31): https://github.com/pola-rs/polars/issues/20947 · Polars 2.0 (streaming padrão): https://pola.rs/posts/announcing-polars-2/
- DuckDB — Memory management (`memory_limit` 80 %, `temp_directory`, spill): https://duckdb.org/2024/07/09/memory-management.html
- numpy — copies and views: https://numpy.org/doc/stable/user/basics.copies.html · `memmap`: https://numpy.org/doc/stable/reference/generated/numpy.memmap.html
- pyarrow — memory and IO: https://arrow.apache.org/docs/python/memory.html · parquet `iter_batches`: https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html
- DuckDB — Python API: https://duckdb.org/docs/api/python/overview
- `array` module: https://docs.python.org/3/library/array.html
