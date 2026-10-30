# Preservação de identidade e prompt de imagem

> Referência da skill `ai-imagem-generativa`.

## 1. As cinco técnicas, na ordem em que devem ser tentadas

### Nível 1 — Não tocar no rosto (segmentação + composição)

Segmenta a pessoa, substitui o fundo, harmoniza cor/luz nas bordas.

- Identidade: **perfeita por construção** (os pixels do rosto são os originais).
- Latência: 0,3–1,5 s local, sem GPU dedicada.
- Custo: ~0.
- Limite: só troca cenário. Não muda roupa, estilo artístico nem época.
- Risco visual: recorte de cabelo e borda com halo; luz do fundo incoerente com a da pessoa.
- Mitigação: matting com refino de borda + transferência de cor dominante do fundo para a pessoa.

**Cubra o máximo de temas aqui.** É a técnica mais subestimada e a que mais entrega em evento.

### Nível 2 — Edição por instrução (image-to-image guiado por texto)

Modelos de edição instrucional preservam bem o sujeito quando a instrução delimita o escopo.

- Identidade: boa a muito boa, cai conforme a força da transformação.
- Latência: 4–15 s (cloud).
- Custo: US$0,01–0,08 por imagem.
- **Prompt precisa dizer o que NÃO mudar.** É a variável de maior impacto.

### Nível 3 — Inpaint fora da máscara facial

Gera tudo exceto a região do rosto, protegida por máscara vinda da detecção facial.

- Identidade: alta.
- Custo: exige máscara precisa; falha em perfil e oclusão.
- Risco: costura visível na fronteira da máscara; exige feather e harmonização.

### Nível 4 — Adaptadores de identidade (GPU)

IP-Adapter FaceID, InstantID, PuLID e sucessores injetam um **embedding facial** no processo de
difusão sobre SDXL ou FLUX. Permitem transformação estilística forte mantendo semelhança.

- Identidade: média a alta, muito sensível a calibração (peso do adaptador, CFG, passos).
- Latência: 8–40 s conforme GPU, resolução e passos.
- Custo: hardware + energia; zero por imagem.
- Trade-off central: **peso alto do adaptador preserva o rosto mas engessa o estilo; peso baixo
  estiliza bem e perde a pessoa.** Esse único parâmetro decide o resultado — calibre com medição.
- Só adote se a POC provar ganho perceptual que justifique GPU no totem.

### Nível 5 — Text-to-image descrevendo a pessoa

Não preserva identidade. Use apenas para gerar **cenários e fundos**, nunca a pessoa.

## 2. Prompt de imagem — estrutura que funciona

```text
[SUJEITO PRESERVADO] + [TRANSFORMAÇÃO] + [CENÁRIO] + [LUZ E CÂMERA] + [QUALIDADE] + [NEGATIVO]
```

Exemplo (tema "Explorador Espacial"):

```text
POSITIVO:
Keep the person's face, facial features, skin tone, hair and expression exactly as in the
input photo. Change only clothing and background: astronaut suit with subtle brand-free
patches, standing inside a bright spacecraft corridor, large window with Earth behind.
Cinematic soft key light from the left matching the original photo's lighting direction,
50mm portrait lens, shallow depth of field, sharp focus on the eyes, photorealistic.

NEGATIVO:
different face, altered facial structure, changed age, changed ethnicity, plastic skin,
extra fingers, deformed hands, asymmetric eyes, crossed eyes, blurry face, watermark, text,
logo, duplicate person, distorted teeth, melted glasses.
```

**Cinco regras aprendidas:**

1. **Diga o que preservar antes de dizer o que mudar.** A ordem importa nos modelos instrucionais.
2. **Amarre a luz ao original** ("matching the original photo's lighting direction") — incoerência
   de iluminação é o que faz a foto "parecer colada" mesmo com rosto perfeito.
3. **Negativo sempre inclui mãos, olhos e texto** — as três falhas mais frequentes.
4. **Prompt é do catálogo, não do usuário.** Texto livre do público em produção é superfície de
   abuso e de imprevisibilidade. Cada tema tem prompt versionado.
5. **Versione o prompt** (`theme_id@v3`) e trate mudança de prompt como mudança de modelo: exige
   comparação contra baseline em `ai-evaluation`.

## 3. Seed e reprodutibilidade

Sem seed fixa não há benchmark: você compara ruído, não modelos.

- **Benchmark:** seed fixa por par (foto, tema). Mesma seed em todos os provedores que aceitam.
- **Produção:** seed aleatória (duas pessoas com o mesmo tema não devem sair idênticas), mas
  **registrada** no telemetry para reproduzir uma reclamação depois.

## 4. Métrica de identidade

Não confie em "ficou bonito". Meça:

| Métrica | Como | Meta sugerida (calibrar na POC) |
|---|---|---|
| **Similaridade facial** | Cosseno entre embeddings do rosto original e do gerado | ≥ 0,55 aceitável · ≥ 0,65 bom (calibrar contra o julgamento humano na Fase 0) |
| **Rosto detectado** | Detector no resultado | 100% — sem rosto é falha automática |
| **Nitidez do rosto** | Variância do laplaciano na ROI facial | ≥ baseline da captura |
| **Anomalia de mãos** | Detector de mão + contagem de dedos, quando visíveis | flag para revisão |
| **Aprovação humana** | Painel de 3 avaliadores, escala 1–5 | ≥ 4,0 de média |

**O número automático só vale depois de correlacionado com o humano.** Na Fase 0, avalie as
mesmas ~60 imagens pelos dois métodos e calcule a correlação; se for fraca, o limiar automático
está errado — e não o contrário. Implementação: skills `visao-computacional` e `ai-evaluation`.

## 5. Catálogo de temas — ficha mínima

```yaml
theme_id: explorador-espacial
version: 3
tecnica: edicao-instrucional        # filtro | segmentacao | edicao | inpaint | adaptador
tier: padrao                        # rapido | padrao | premium
prompt_ref: prompts/explorador-espacial.v3.txt
negativo_ref: prompts/_negativo-base.v2.txt
resolucao: [1200, 1800]
sla_ms: 12000
fallback_theme: vintage-filtro      # tema determinístico equivalente
consent_required: true
```

Um tema sem `fallback_theme` determinístico não entra em produção: é um caminho sem saída quando
o provedor cai.
