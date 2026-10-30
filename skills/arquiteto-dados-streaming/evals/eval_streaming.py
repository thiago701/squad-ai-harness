"""Evals para arquiteto-dados-streaming."""
import pytest


DECISAO_MATRIX = {
    "kinesis": {
        "replay": True, "multi_consumer": True, "serverless": True,
        "ecossistema_kafka": False, "custo": "medio"
    },
    "msk": {
        "replay": True, "multi_consumer": True, "serverless": False,
        "ecossistema_kafka": True, "custo": "alto"
    },
    "sqs": {
        "replay": False, "multi_consumer": False, "serverless": True,
        "ecossistema_kafka": False, "custo": "baixo"
    },
    "eventbridge": {
        "replay": False, "multi_consumer": True, "serverless": True,
        "ecossistema_kafka": False, "custo": "baixo"
    },
}


def test_kinesis_tem_replay():
    assert DECISAO_MATRIX["kinesis"]["replay"] is True

def test_sqs_sem_replay():
    assert DECISAO_MATRIX["sqs"]["replay"] is False

def test_msk_tem_ecossistema_kafka():
    assert DECISAO_MATRIX["msk"]["ecossistema_kafka"] is True

def test_kinesis_nao_kafka():
    assert DECISAO_MATRIX["kinesis"]["ecossistema_kafka"] is False

def test_sqs_sem_multi_consumer():
    assert DECISAO_MATRIX["sqs"]["multi_consumer"] is False

def test_kinesis_serverless():
    assert DECISAO_MATRIX["kinesis"]["serverless"] is True

def test_msk_nao_serverless():
    assert DECISAO_MATRIX["msk"]["serverless"] is False

def test_custo_ordem():
    """MSK > Kinesis > SQS/EventBridge em custo."""
    custos = {"alto": 3, "medio": 2, "baixo": 1}
    assert custos[DECISAO_MATRIX["msk"]["custo"]] > custos[DECISAO_MATRIX["kinesis"]["custo"]]
    assert custos[DECISAO_MATRIX["kinesis"]["custo"]] > custos[DECISAO_MATRIX["sqs"]["custo"]]

def test_fifo_sqs_garante_ordem():
    """SQS FIFO garante ordem e exactly-once (300 TPS)."""
    sqs_fifo = {"ordenado": True, "exactly_once": True, "tps_max": 300}
    assert sqs_fifo["ordenado"] is True

def test_kappa_simpler_than_lambda():
    """Kappa architecture tem menos pipelines que Lambda."""
    lambda_arch = {"pipelines": 2}  # speed + batch
    kappa_arch = {"pipelines": 1}   # só streaming
    assert kappa_arch["pipelines"] < lambda_arch["pipelines"]
