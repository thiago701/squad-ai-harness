# -*- coding: utf-8 -*-
"""Camadas dinâmicas: C1 (provedor in-process, JUnit) e C2 (replay HTTP pelo Gateway).

C1 — roda o verificador do provedor declarado no contrato (ex.: Maven) e lê o arquivo
     "observado" que ele grava. O JUnit simula o Gateway a partir do MESMO template SAM
     (rotas, autorizador, CORS) e usa dublê de persistência: comprova a implementação,
     NÃO o Gateway implantado nem o banco real.
C2 — envia as interações ao endpoint do Gateway num ambiente autorizado pelo contrato.
     Credenciais só por variável de ambiente (CDC_TOKEN_<IDENTIDADE>); nada é gravado.
     Em ambiente marcado `producao: true` só rodam métodos seguros (GET/OPTIONS/HEAD).
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from . import INFO, PENDENTE, QUEBRA, Achado, ResultadoCamada
from .avaliacao import avaliar
from .modelo import METODOS_SEGUROS, Contrato, substituir


def hash_contrato(contrato: Contrato) -> str:
    return hashlib.sha256(contrato.arquivo.read_bytes()).hexdigest()[:16]


def _cors_na_resposta(contrato: Contrato, gateway) -> bool:
    return bool(contrato.navegador and gateway is not None and getattr(gateway, "tipo_api", "http") == "rest")


def julgar(camada: str, contrato: Contrato, observados: list[dict], cors_na_resposta: bool = False) -> list[Achado]:
    """cors_na_resposta: REST API + consumidor de navegador — a resposta REAL tem de trazer
    Access-Control-Allow-Origin (o Gateway REST não acrescenta em integração proxy)."""
    por_id = {o.get("id"): o for o in observados}
    variaveis = contrato.variaveis_base()
    achados: list[Achado] = []
    for it in contrato.interacoes:
        obs = por_id.get(it.id)
        if obs is None:
            achados.append(Achado(camada, QUEBRA, "C-NAO-EXECUTADA", it.id,
                                  "o verificador não registrou esta interação"))
            continue
        if obs.get("pulada"):
            achados.append(Achado(camada, PENDENTE, "C-PULADA", it.id, f"não executada: {obs['pulada']}"))
            continue
        novos, capturas = avaliar(camada, it, obs, variaveis, contrato.enums_fechados)
        achados.extend(novos)
        variaveis.update(capturas)
        if (cors_na_resposta and it.metodo != "OPTIONS" and str(obs.get("origem_resposta", "")).startswith(("handler", "gateway-implantado"))
                and int(obs.get("status") or 0) < 500):
            origem = str(contrato.consumidor.get("origem_navegador", ""))
            valor = {str(k).lower(): str(v) for k, v in (obs.get("headers") or {}).items()}.get("access-control-allow-origin")
            if valor not in (origem, "*"):
                achados.append(Achado(camada, QUEBRA, "C-CORS-RESPOSTA", it.id,
                                      f"REST API com proxy: a resposta não traz Access-Control-Allow-Origin para {origem} "
                                      f"(veio {valor!r}) — o navegador descarta a resposta mesmo com status certo"))
    return achados


# ----------------------------------------------------------------------------- C1
def _resolver_comando(comando: list[str], cwd: Path) -> list[str] | None:
    exe = comando[0]
    if shutil.which(exe):
        return comando
    if exe == "mvn":
        for wrapper in ("mvnw.cmd", "mvnw") if os.name == "nt" else ("mvnw",):
            if (cwd / wrapper).is_file():
                return [str(cwd / wrapper), *comando[1:]]
    return None


def rodar_verificador(contrato: Contrato, chave_comando: str, camada: str, timeout_s: int = 900,
                      entrada: Path | None = None, gateway=None) -> ResultadoCamada:
    cfg = contrato.provedor.get(chave_comando) or {}
    alcance = ("implementação real do backend; Gateway SIMULADO a partir do template SAM; persistência em dublê "
               "(não comprova Gateway implantado, banco real nem ordenação feita pelo banco)")
    res = ResultadoCamada(camada=camada, executada=False, alcance=alcance)
    if not cfg.get("comando") and cfg.get("runner") not in ("python", "node"):
        res.motivo_nao_execucao = f"contrato não declara provedor.{chave_comando}"
        return res
    if cfg.get("runner") in ("python", "node"):
        return _rodar_runner(contrato, cfg, camada, gateway, res)
    cwd = contrato.raiz_repo / cfg.get("cwd", ".")
    comando = _resolver_comando([str(c) for c in cfg["comando"]], cwd)
    if comando is None:
        res.motivo_nao_execucao = f"executável '{cfg['comando'][0]}' indisponível nesta máquina (nem wrapper)"
        return res
    observado = contrato.raiz_repo / cfg.get("observado", contrato.provedor.get("verificador_inprocess", {})
                                                .get("observado", ""))
    # não apaga o observado anterior (pastas montadas podem proibir exclusão): exige que seja mais NOVO que esta execução
    marca = time.time() - 1
    inicio = time.monotonic()
    env = {**os.environ, "CDC_CONTRATO": str(contrato.arquivo.resolve())}
    if entrada is not None:
        env["CDC_ENTRADA"] = str(entrada.resolve())
    try:
        proc = subprocess.run(comando, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout_s,
                              encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        res.motivo_nao_execucao = f"verificador excedeu {timeout_s}s"
        return res
    res.duracao_s = round(time.monotonic() - inicio, 2)
    res.extras["codigo_saida"] = proc.returncode
    res.extras["saida_final"] = (proc.stdout + proc.stderr)[-1500:]
    if not observado.is_file() or observado.stat().st_mtime < marca:
        if "ADAPTE criarHandler" in res.extras["saida_final"] or "ADAPTE criarHandler" in proc.stdout:
            res.motivo_nao_execucao = "verificador do provedor ainda não adaptado: edite criarHandler() (dublês nas portas de saída)"
        else:
            res.motivo_nao_execucao = (f"o verificador terminou (exit {proc.returncode}) sem gravar {observado.name} — "
                                       "build/dependências/JDK, não o contrato")
        return res
    dados = json.loads(observado.read_text(encoding="utf-8"))
    res.extras["observado"] = {k: v for k, v in dados.items() if k != "interacoes"}
    if dados.get("contrato_hash") != hash_contrato(contrato):
        res.motivo_nao_execucao = "observado gravado com outra versão do contrato (hash diverge)"
        return res
    res.executada = True
    res.achados = julgar(camada, contrato, dados.get("interacoes") or [], _cors_na_resposta(contrato, gateway))
    if proc.returncode != 0 and not any(a.severidade == QUEBRA for a in res.achados):
        res.achados.append(Achado(camada, QUEBRA, "C-SUITE-FALHOU", None,
                                  f"a suíte do provedor falhou (exit {proc.returncode}) — veja saida_final"))
    return res


def _rodar_runner(contrato: Contrato, cfg: dict, camada: str, gateway, res: ResultadoCamada) -> ResultadoCamada:
    """C1 para Python/Node: simulador de Gateway (Python) + runner do stack (JSON por linha)."""
    from .simulador import comando_runner, conduzir
    try:
        cmd, _, _ = comando_runner(contrato, cfg)
    except ValueError as exc:
        res.motivo_nao_execucao = str(exc)
        return res
    if not shutil.which(cmd[0]) and not Path(cmd[0]).exists():
        res.motivo_nao_execucao = f"interpretador '{cmd[0]}' indisponível nesta máquina"
        return res
    res.alcance = (f"implementação real ({cfg['runner']}) chamada in-process; Gateway SIMULADO a partir do modelo "
                   f"normalizado; {cfg.get('persistencia', 'portas de saída conforme a fábrica')} (não comprova "
                   "Gateway implantado nem dependências reais)")
    inicio = time.monotonic()
    try:
        observados, meta = conduzir(contrato, gateway.para_dict() if gateway is not None else None, cfg)
    except RuntimeError as exc:
        texto = str(exc)
        res.motivo_nao_execucao = ("verificador do provedor ainda não adaptado: edite a fábrica (criar_handler/criarHandler) "
                                   "com dublês nas portas de saída" if "ADAPTE criarHandler" in texto else texto[:600])
        return res
    res.duracao_s = round(time.monotonic() - inicio, 2)
    from .nucleo import pasta_trabalho
    destino = pasta_trabalho(contrato.raiz_repo) / f"observado-{contrato.nome}.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps({"contrato_hash": hash_contrato(contrato), "transporte": f"runner {meta.get('runner')} "
                                   f"{meta.get('versao')} ({meta.get('modo')})", "gateway": "simulado do modelo normalizado",
                                   "persistencia": cfg.get("persistencia", ""), "interacoes": observados},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    res.extras["observado"] = {"transporte": f"runner {meta.get('runner')} {meta.get('versao')}",
                               "gateway": "simulado do modelo normalizado", "persistencia": cfg.get("persistencia", "")}
    res.executada = True
    res.achados = julgar(camada, contrato, observados, _cors_na_resposta(contrato, gateway))
    return res


# ----------------------------------------------------------------------------- C2
def _host_permitido(url: str, ambiente: dict) -> bool:
    host = urllib.parse.urlparse(url).hostname or ""
    padroes = ambiente.get("hosts_permitidos")
    if padroes is None:
        base = ambiente.get("url_base_padrao")
        return bool(base) and urllib.parse.urlparse(base).hostname == host
    return any(fnmatch.fnmatch(host, p) for p in padroes)


def _var_token(identidade: str) -> str:
    return "CDC_TOKEN_" + identidade.upper().replace("-", "_")


def replay_http(contrato: Contrato, alvo: str | None, nome_ambiente: str | None,
                permitir_escrita: bool, gateway=None) -> ResultadoCamada:
    alcance = "funcionamento pelo endpoint do Gateway no ambiente informado (Gateway, autorizador, backend e dependências reais)"
    res = ResultadoCamada(camada="C2", executada=False, alcance=alcance)
    ambientes = contrato.bruto.get("ambientes") or {}
    if not nome_ambiente or nome_ambiente not in ambientes:
        res.motivo_nao_execucao = f"ambiente não informado ou não declarado no contrato ({sorted(ambientes)})"
        return res
    ambiente = ambientes[nome_ambiente] or {}
    alvo = alvo or ambiente.get("url_base_padrao")
    if not alvo:
        res.motivo_nao_execucao = "sem --alvo (URL base do Gateway)"
        return res
    if not _host_permitido(alvo, ambiente):
        res.motivo_nao_execucao = f"host de {alvo} fora dos hosts permitidos do ambiente '{nome_ambiente}'"
        return res
    producao = bool(ambiente.get("producao"))
    identidades = {it.token for it in contrato.interacoes if it.token and it.token != "invalido"}
    faltam = sorted(_var_token(i) for i in identidades if not os.environ.get(_var_token(i)))
    if faltam:
        res.motivo_nao_execucao = f"credenciais ausentes: {faltam} (defina as variáveis; nunca no arquivo)"
        return res
    timeout = float(contrato.consumidor.get("timeout_ms", 10000)) / 1000
    variaveis = contrato.variaveis_base()
    observados: list[dict] = []
    inicio = time.monotonic()
    for it in contrato.interacoes:
        escrita = it.metodo not in METODOS_SEGUROS
        if escrita and (producao or not permitir_escrita):
            motivo = "ambiente de produção (só métodos seguros)" if producao else "escrita não autorizada (--permitir-escrita)"
            observados.append({"id": it.id, "pulada": motivo})
            continue
        req = substituir(it.requisicao, variaveis)
        url = alvo.rstrip("/") + req.get("caminho", "/")
        if req.get("query"):
            url += "?" + urllib.parse.urlencode(req["query"])
        headers = {str(k): str(v) for k, v in (req.get("headers") or {}).items()}
        if contrato.navegador and not any(k.lower() == "origin" for k in headers):
            headers["Origin"] = str(contrato.consumidor.get("origem_navegador", ""))  # navegador sempre manda Origin
        if it.token:
            headers["Authorization"] = "Bearer " + (os.environ.get(_var_token(it.token), "") if it.token != "invalido"
                                                    else "token-invalido")
        corpo = req.get("corpo")
        dados = json.dumps(corpo).encode() if corpo is not None else None
        pedido = urllib.request.Request(url, data=dados, method=it.metodo, headers=headers)
        try:
            with urllib.request.urlopen(pedido, timeout=timeout) as r:  # noqa: S310 - host validado acima
                obs = {"status": r.status, "headers": dict(r.headers), "corpo": r.read().decode("utf-8", "replace")}
        except urllib.error.HTTPError as e:
            obs = {"status": e.code, "headers": dict(e.headers or {}), "corpo": e.read().decode("utf-8", "replace")}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            res.motivo_nao_execucao = f"endpoint inacessível em '{it.id}': {type(e).__name__}"
            return res
        obs.update(id=it.id, origem_resposta="gateway-implantado")
        observados.append(obs)
        _, capturas = avaliar("C2", it, obs, variaveis, contrato.enums_fechados)
        variaveis.update(capturas)
    res.duracao_s = round(time.monotonic() - inicio, 2)
    res.executada = True
    res.achados = julgar("C2", contrato, observados, _cors_na_resposta(contrato, gateway))
    ids_req = sorted({o["headers"].get("apigw-requestid") or o["headers"].get("x-amzn-requestid") or ""
                      for o in observados if o.get("headers")} - {""})
    res.extras.update(alvo_host=urllib.parse.urlparse(alvo).hostname, ambiente=nome_ambiente,
                      ids_requisicao_gateway=ids_req[:5])
    if any(o.get("pulada") for o in observados):
        res.achados.append(Achado("C2", INFO, "C2-PARCIAL", None,
                                  "replay parcial: interações de escrita não executadas neste ambiente"))
    return res
