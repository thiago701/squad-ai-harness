# Pipeline de imagem — receitas determinísticas

> Referência da skill `visao-computacional`.

## 1. Contrato de imagem (derive do destino, não da origem)

| Destino | Dimensão | Proporção | Espaço de cor | Formato |
|---|---|---|---|---|
| Impressão 10×15 cm @ 300 dpi | 1200 × 1800 | 2:3 | sRGB | JPEG q95 |
| Tira 5×15 cm @ 300 dpi | 600 × 1800 | 1:3 | sRGB | JPEG q95 |
| Tela do totem / QR | 1080 lado maior | 2:3 | sRGB | JPEG q85 |
| Entrada da IA | ≥ 1536 lado maior | 2:3 | sRGB | PNG ou JPEG q95 |

Trave a proporção **uma vez**, no início, e propague. Cada reenquadramento posterior é uma chance
de cortar a testa de alguém.

## 2. Crop facial estável

```python
def crop_retrato(img, bbox, landmarks, alvo=(1200, 1800)):
    """Âncora entre os olhos, deslocada para cima; margem mínima no topo."""
    ex, ey = centro_dos_olhos(landmarks)
    ar = alvo[0] / alvo[1]                       # 0.666...
    altura = min(img.height, bbox.h / 0.32)      # rosto ocupa ~32% da altura final
    largura = altura * ar
    cx = ex
    cy = ey + altura * 0.08                      # olhos ~ 42% do topo
    caixa = clamp_para_dentro(img, cx, cy, largura, altura)
    return img.crop(caixa).resize(alvo, Image.LANCZOS)
```

**Estabilidade importa mais que perfeição:** duas fotos da mesma pessoa devem enquadrar igual.
Suavize o bbox entre frames no preview (média móvel) para o retângulo não "tremer" na tela.

## 3. Ordem canônica das operações

```text
1. exif_transpose            (antes de qualquer coisa)
2. convert("RGB")
3. detectar na cópia reduzida (lado maior 640 px) → escalar coordenadas de volta
4. validar (nitidez, exposição, tamanho do rosto)
5. crop com proporção travada
6. resize LANCZOS para o alvo
7. correção de cor leve
8. → IA
9. validar saída
10. pós + moldura
11. derivadas (tela, impressão)
```

Inverter 3 e 5 (detectar depois de cortar) é o bug mais comum: você corta antes de saber onde
está o rosto.

## 4. Matting e composição de fundo

```python
mask = matting_model(img)                 # alfa em [0,1], ONNX Runtime
mask = cv2.GaussianBlur(mask, (0, 0), 1.5)      # feather 2–4 px
mask = corrige_halo(mask, img)                   # erode 1px onde o alfa é intermediário

fundo = carrega_cenario(theme).resize(img.size, Image.LANCZOS)
out   = img * mask[..., None] + fundo * (1 - mask[..., None])

out = harmoniza_cor(out, fundo, intensidade=0.18)   # temperatura dominante do fundo
out = sombra_de_contato(out, mask, opacidade=0.25)
```

Sem os dois últimos passos o resultado é tecnicamente correto e visualmente falso. É o que separa
"recorte" de "composição".

## 5. Moldura e branding

- Camada PNG com alfa, **na resolução final exata** (1200×1800). Nada de escalar moldura.
- Área de segurança: margem de 5 mm (≈ 60 px) que a impressora pode cortar.
- Logo do evento em camada separada, posição configurável por evento — não recompile para trocar.
- Texto: renderize com fonte embarcada; fonte ausente na máquina do totem = layout quebrado no
  meio do evento.

## 6. Testes de regressão visual

```python
# Fixtures versionadas: 12 fotos cobrindo tom de pele, idade, óculos, chapéu,
# perfil, luz baixa, contraluz, duas pessoas, sem rosto.
def test_pipeline_estavel(fixture):
    saida = pipeline(fixture.path)
    assert phash(saida) == fixture.phash_esperado    # hash perceptual, tolerância pequena
    assert saida.size == (1200, 1800)
```

Hash perceptual pega regressão de crop e de cor que um `assert` de tamanho deixa passar.
Guarde as fixtures no repositório — com consentimento documentado de quem aparece nelas, ou use
rostos sintéticos.

## 7. Desempenho — o que realmente custa

| Prática | Ganho típico |
|---|---|
| Detectar em 640 px e escalar coordenadas | 5–10× na detecção |
| Manter o modelo ONNX carregado (não recarregar por foto) | 200–800 ms por foto |
| `cv2.setNumThreads()` alinhado aos núcleos reais | evita thrashing em máquina modesta |
| Trabalhar em `uint8` até o último passo | metade da memória |
| Evitar ida e volta PIL↔NumPy↔cv2 | 20–80 ms por conversão descartada |
