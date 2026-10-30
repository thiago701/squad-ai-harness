# VRAM, quantização e otimização — o que cada técnica custa

> Referência da skill `inferencia-gpu-local`. **Nenhuma técnica desta página deve ser adotada sem
> medição comparativa contra o baseline em fp16.** Toda otimização de inferência é uma troca; a
> maioria cobra em qualidade do rosto — exatamente onde o photobooth não pode pagar.

## 1. Como medir de verdade

```python
import torch
torch.cuda.reset_peak_memory_stats()
_ = pipe(**pior_caso)                       # maior resolução, todos os adaptadores, upscaler
pico_gb = torch.cuda.max_memory_allocated() / 1024**3
print(f"pico={pico_gb:.2f} GB  reservado={torch.cuda.max_memory_reserved()/1024**3:.2f} GB")
```

Meça o **pior caso**, com o processo já aquecido, e repita 5 vezes — a primeira execução inclui
alocações de compilação que não se repetem.

## 2. Técnicas, em ordem de "grátis" para "cobra caro"

| Técnica | Economia de VRAM | Efeito na latência | Custo em qualidade | Veredito |
|---|---|---|---|---|
| **VAE slicing / tiling** | Média, no pico do decoder | Levemente pior | Nenhum | ✅ Adote |
| **Attention eficiente (SDPA/Flash)** | Média | **Melhor** | Nenhum | ✅ Adote |
| **fp16 / bf16** (contra fp32) | ~metade | Melhor | Desprezível | ✅ Padrão |
| **Menos passos de amostragem** | Nenhuma | **Muito melhor** | Real, mas mensurável | ✅ Calibre — é a melhor alavanca |
| **`torch.compile`** | Nenhuma | Melhor após warm-up | Nenhum | ⚠️ Warm-up longo; vale em serviço residente |
| **Modelo destilado / few-step** | Depende | **Muito melhor** | Varia por modelo | ⚠️ Meça: às vezes é o melhor negócio |
| **Quantização de pesos (8-bit)** | Alta | Neutra a melhor | Pequena, geralmente aceitável | ⚠️ Meça no rosto |
| **Quantização agressiva (4-bit)** | Muito alta | Melhor | **Visível em pele e olhos** | ❌ Não para retrato |
| **CPU offload sequencial** | Muito alta | **Muito pior** | Nenhum | ❌ Mata o SLA do evento |
| **Resolução menor + upscale** | Alta | Melhor | Depende do upscaler | ⚠️ Compare com gerar direto |

**A alavanca mais subestimada é o número de passos.** Reduzir passos costuma dar mais ganho de
latência, com menos dano à identidade, do que quantizar. Calibre passos primeiro, quantize depois.

## 3. Protocolo de aceitação de uma otimização

Espelha o §26 do briefing (loop autônomo de melhoria):

1. **Baseline:** o mesmo conjunto de ≥ 30 pares (foto, tema), seed fixa, fp16, configuração atual.
2. **Candidata:** aplique **uma** técnica por vez. Duas de uma vez impede atribuir o efeito.
3. **Meça:** p50/p95 de latência, VRAM pico, similaridade facial média, nitidez do rosto, taxa de
   artefato, taxa de OOM.
4. **Aceite** apenas se houver ganho comprovável em latência, VRAM ou custo **sem regressão
   crítica** em identidade (queda > 0,03 na similaridade média é 🟡; > 0,06 é ❌).
5. **Registre** em ADR com os números dos dois lados. Otimização sem número registrado é folclore.

## 4. Armadilhas de VRAM

| Sintoma | Causa provável | Correção |
|---|---|---|
| OOM só no último passo | Pico do VAE/decoder | VAE slicing/tiling |
| OOM depois de horas rodando | Fragmentação | Reiniciar worker entre eventos; reservar folga |
| Latência errática (5 s ↔ 40 s) | Swap/offload silencioso | Reduzir residentes; caber sem offload |
| OOM ao trocar de tema | Troca de LoRA/adaptador em runtime | Pré-carregar todos os adaptadores do catálogo |
| VRAM some sem uso | Compositor do SO + navegador do kiosk | Descontar do orçamento; medir com o kiosk aberto |
| Duas gerações simultâneas travam | Concorrência na mesma GPU | Fila serializada, worker único |

## 5. Windows como plataforma de totem

- Driver e runtime CUDA **fixados por versão** — atualização automática no meio da temporada de
  eventos já quebrou pipeline em produção. Desative update automático de driver no totem.
- Modo de energia em desempenho máximo; suspensão e hibernação desligadas.
- O compositor de janelas e o navegador do kiosk consomem VRAM: meça o orçamento **com o kiosk
  rodando**, não num console limpo.
- Serviço do worker com restart automático e reinício direto no kiosk após reboot.
- Antivírus corporativo varrendo a pasta de pesos adiciona segundos ao carregamento: exclua a
  pasta de modelos da varredura em tempo real.

## 6. Licença dos pesos — verifique antes de codar

Modelos abertos têm licenças **diferentes entre si**, e várias restringem uso comercial ou exigem
condições específicas. Antes de adotar qualquer peso:

1. Leia a licença do checkpoint **e** de cada LoRA/adaptador — são licenças independentes.
2. Confirme se o uso é comercial (evento pago é uso comercial).
3. Registre origem, versão, hash e licença em `docs/ATTRIBUTIONS.md`.
4. Na dúvida, escale para decisão humana — não presuma. Ver regra **A8** de `RULES.md`.
