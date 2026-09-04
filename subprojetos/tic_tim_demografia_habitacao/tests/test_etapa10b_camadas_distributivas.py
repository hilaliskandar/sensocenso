import pandas as pd

from tic_tim_demografia.etapa10b_corrente import (
    _agregar_arranjo,
    _agregar_fcu,
    _flag_fcu,
    _flag_rr,
    _rr,
)


def test_agregar_arranjo_preserva_apenas_pares_validos():
    base = pd.DataFrame(
        {
            "codigo_setor": ["1", "2", "3", "4"],
            "codigo_ibge": ["10", "10", "20", "20"],
            "v01179_domicilios_sem_conjuge": [10, 5, 4, None],
            "v01188_resp_mulher_sem_conjuge": [6, None, 3, 1],
        }
    )
    out = _agregar_arranjo(base)
    assert out.loc["10", "dom_sem_conjuge_pub_urbano"] == 10
    assert out.loc["10", "dom_sem_conjuge_resp_mulher_pub_urbano"] == 6
    assert out.loc["10", "setores_validos_parentesco"] == 1
    assert out.loc["10", "cobertura_setorial_parentesco"] == 0.5
    assert out.loc["20", "pct_dom_sem_conjuge_resp_mulher_urbano"] == 0.75


def test_agregar_fcu_usa_mesmo_universo_no_denominador():
    base = pd.DataFrame(
        {
            "codigo_setor": ["1", "2", "3"],
            "codigo_ibge": ["10", "10", "20"],
            "POP_TOTAL": [100, 300, 200],
            "DPPO": [40, 100, 80],
        }
    )
    out = _agregar_fcu(base, {"2", "3"})
    assert out.loc["10", "pop_urbana_malha"] == 400
    assert out.loc["10", "pop_fcu_urbana"] == 300
    assert out.loc["10", "pct_pop_urbana_em_fcu"] == 0.75
    assert out.loc["20", "pct_setores_urbanos_fcu"] == 1.0


def test_rr_e_flags_sao_descritivos():
    serie = pd.Series([0.09, 0.10, 0.11])
    rr = _rr(serie, 0.10)
    assert rr.tolist() == [0.9, 1.0, 1.0999999999999999]
    assert _flag_rr(0.89) == ">=10% abaixo da referência"
    assert _flag_rr(1.00) == "próximo da referência"
    assert _flag_rr(1.11) == ">=10% acima da referência"
    assert _flag_fcu(0.0) == "Sem população FCU identificada"
    assert _flag_fcu(0.05) == "FCU <10% pop urbana"
    assert _flag_fcu(0.10) == "FCU >=10% pop urbana"
