from tic_tim_demografia.fontes.sidra_descritor import (
    extrair_classificacoes,
    localizar_categoria,
    localizar_classificacao,
    resumo_descritor,
)


def fixture_descritor():
    return {
        "Classificacoes": [
            {
                "Codigo": 2,
                "Nome": "Sexo",
                "Categorias": [
                    {"Codigo": 0, "Nome": "Total"},
                    {"Codigo": 4, "Nome": "Homens"},
                    {"Codigo": 5, "Nome": "Mulheres"},
                ],
            },
            {
                "Codigo": 287,
                "Nome": "Grupos de idade",
                "Categorias": [
                    {"Codigo": 100, "Nome": "0 a 4 anos"},
                    {"Codigo": 101, "Nome": "5 a 9 anos"},
                    {"Codigo": 199, "Nome": "Total"},
                ],
            },
        ]
    }


def test_extrai_classificacoes_sem_depender_de_posicao_fixa():
    cls = extrair_classificacoes({"wrapper": [fixture_descritor()]})
    assert {c.nome for c in cls} == {"Sexo", "Grupos de idade"}


def test_localiza_sexo_e_total_por_rotulo():
    cls = extrair_classificacoes(fixture_descritor())
    sexo = localizar_classificacao(cls, termos_nome=["sexo"])
    total = localizar_categoria(sexo, nomes_exatos=["Total"])
    assert sexo.codigo == "2"
    assert total.codigo == "0"


def test_localiza_grupo_idade_por_nome_sem_codigo_hardcoded():
    cls = extrair_classificacoes(fixture_descritor())
    idade = localizar_classificacao(cls, termos_nome=["grupo de idade", "grupos de idade"])
    cat = localizar_categoria(idade, termos=["0 a 4"])
    assert cat.codigo == "100"


def test_resumo_preserva_codigos_e_rotulos():
    resumo = resumo_descritor(fixture_descritor())
    assert resumo["n_classificacoes_detectadas"] == 2
    assert resumo["classificacoes"][0]["codigo"] == "2"
