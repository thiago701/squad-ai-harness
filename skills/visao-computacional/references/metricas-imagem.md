# Métricas objetivas de imagem e calibração de limiar

> Referência da skill `visao-computacional`. Estas métricas alimentam a skill `ai-evaluation`.

## 1. Catálogo de métricas

| Métrica | Fórmula / método | Faixa útil | O que detecta |
|---|---|---|---|
| **Nitidez** | Variância do laplaciano na ROI facial | 0–2000+ | Foto tremida, desfoco, upscale macio |
| **Exposição** | Média do canal Y + % de pixels clipados | média 40–215 | Contraluz, escuro, estourado |
| **Contraste** | Desvio padrão de Y | > 25 | Foto lavada |
| **Área do rosto** | `bbox.area / img.area` | ≥ 0,04 | Pessoa longe demais |
| **Pose (yaw/pitch)** | Landmarks → PnP | \|yaw\| ≤ 35° | Perfil que quebra a geração |
| **Similaridade facial** | Cosseno entre embeddings normalizados | −1 a 1 | Perda de identidade |
| **Δ nitidez** | nitidez(saída) / nitidez(entrada) | ≥ 0,8 | Geração que borrou o rosto |
| **Anomalia de mãos** | Detector de mão + contagem de dedos | flag | Dedos extras/fundidos |
| **Simetria ocular** | Distância e alinhamento dos landmarks dos olhos | desvio ≤ 8% | Olhos tortos gerados |
| **Ruído** | Estimativa de sigma em região lisa | — | Modelo com passos insuficientes |

## 2. Calibração — o passo que quase todo mundo pula

Um limiar copiado de um blog reprova gente real. Calibre assim:

1. Monte um conjunto de **≥ 60 pares** (entrada, saída) cobrindo tom de pele, idade, óculos,
   chapéu, barba, iluminação de festa (baixa luz, contraluz, luz colorida).
2. Faça **3 pessoas** avaliarem cada saída de 1 a 5 em duas dimensões: *"parece com a pessoa?"* e
   *"a imagem está bem feita?"*. Calcule a concordância entre avaliadores (descarte o item se a
   dispersão for alta).
3. Calcule a **correlação** entre cada métrica automática e a nota humana.
4. Escolha o limiar no ponto que maximiza o equilíbrio entre reprovar imagem ruim e não reprovar
   imagem boa (curva precisão/recall, não "chute redondo").
5. **Registre a correlação no relatório.** Uma métrica com correlação fraca não deve gatilhar
   decisão automática — ela vira apenas um sinal para revisão.

> Se a similaridade facial automática não correlacionar com a percepção humana no seu conjunto,
> o limiar está errado — não as pessoas. Reporte isso honestamente na POC.

## 3. Viés — checagem obrigatória

Reporte a taxa de falha **por subgrupo**, não só a média:

| Subgrupo | Taxa de detecção | Similaridade média | Taxa de reprovação |
|---|---|---|---|
| Pele clara / luz boa | | | |
| Pele escura / luz boa | | | |
| Pele clara / luz baixa | | | |
| Pele escura / luz baixa | | | |
| Com óculos | | | |
| Acima de 60 anos | | | |
| Criança | | | |

Diferença > 15 pontos entre subgrupos é 🟡 e precisa de ação (melhor iluminação no totem, outro
detector, limiar adaptativo). Um totem que funciona pior para parte do público é um defeito de
produto, não uma limitação aceitável.

## 4. Implementação sem dependência pesada

- Detecção e landmarks: modelo ONNX pequeno via `onnxruntime` (CPU). Evita arrastar framework de
  deep learning inteiro para o totem.
- Embedding facial: modelo ONNX de reconhecimento facial (512-D, L2-normalizado). **Em memória,
  descartado ao fim da sessão.**
- Métricas clássicas: `cv2` + `numpy`, sem dependência extra.
- Fixe versão e **hash** dos pesos baixados; peso de origem desconhecida é supply chain.

## 5. Saída padronizada (consumida por `ai-evaluation`)

```json
{
  "session_id": "…",
  "theme_id": "explorador-espacial@v3",
  "provider": "…", "model": "…", "seed": 12345,
  "entrada": {"nitidez": 412.7, "exposicao_media": 128.4, "area_rosto": 0.081, "yaw": -6.2},
  "saida":   {"nitidez": 388.1, "rosto_detectado": true, "similaridade": 0.63,
              "delta_nitidez": 0.94, "simetria_ocular": 0.03, "anomalia_maos": false},
  "veredito": "aprovada",
  "latencia_ms": {"validar": 71, "preparar": 132, "gerar": 9840, "pos": 240},
  "custo_usd": 0.04
}
```

Uma linha JSON por imagem, append-only. É o insumo de todo o benchmark — e o que permite
responder "por que a foto da mesa 12 saiu ruim?" três semanas depois.
