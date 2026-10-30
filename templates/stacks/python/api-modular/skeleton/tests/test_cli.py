from taskbox.adaptadores.cli import main, montar_parser


def test_cli_listar_vazio(capsys):
    assert main(["listar"]) == 0
    assert "sem pendencias" in capsys.readouterr().out


def test_cli_criar_e_erro_de_dominio(capsys):
    assert main(["criar", "nova tarefa valida"]) == 0
    assert main(["criar", "ab"]) == 2


def test_parser_exige_comando():
    parser = montar_parser()
    argumentos = parser.parse_args(["concluir", "abc-123"])
    assert argumentos.comando == "concluir" and argumentos.identificador == "abc-123"
