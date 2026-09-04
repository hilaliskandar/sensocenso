import pandas as pd
import pytest

from tic_tim_demografia.etapa11a_tabelas import construir_t01, construir_t06


def test_construir_t01_calcula_crescimento_e_participacoes():
    linhas = []
    for codigo, municipio in (("10", "A"), ("20", "B")):
        for ano, total, jovens, idosos in (
            (2000, 100, 30, 10),
            (2010, 120, 25, 18),
            (2022, 150, 24, 30),
        ):
            linhas.append(
                {
                    "codigo_ibge": codigo,
                    "ano": ano,
                    "pop_0_14": jovens,
                    "pop_15_59": total - jovens - idosos,
                    "pop_60_mais": idosos,
                    "pop_total_harmonizada": total,
                    "municipio_config": municipio,
                    "coroa": "x",
                    "razao_envelhecimento": 100 * idosos / jovens,
                }
            )
    # A função exige o universo de produção, então replica os dois casos em 30 códigos.
    base2 = pd.DataFrame(linhas)
    blocos = []
    for i in range(15):
        b = base2.copy()
        b["codigo_ibge"] = b["codigo_ibge"].map(lambda x: str(int(x) + i * 100))
        b["municipio_config"] = b["municipio_config"] + str(i)
        blocos.append(b)
    out = construir_t01(pd.concat(blocos, ignore_index=True))
    a = out.loc[out["municipio"].eq("A0")].iloc[0]
    assert a["crescimento_pop_2000_2010_pct"] == pytest.approx(20.0)
    assert a["crescimento_pop_2010_2022_pct"] == pytest.approx(25.0)
    assert a["pct_60_mais_2022"] == pytest.approx(20.0)


def test_construir_t06_preserva_8073_no_denominador():
    codigos = [str(3500000 + i) for i in range(30)]
    quantidades = [269] * 29 + [272]
    linhas = []
    n = 0
    for codigo, qtd in zip(codigos, quantidades, strict=True):
        for j in range(qtd):
            n += 1
            linhas.append(
                {
                    "codigo_setor": f"{n:015d}",
                    "codigo_ibge": codigo,
                    "municipio": f"M{codigo}",
                    "FLAG_UNIVERSO_INTEGRADO": True,
                    "CONVERGENCIA_3_OU_4": 1 if j == 0 else 0,
                    "POP_TOTAL": 100,
                    "DPPO": 40,
                }
            )
    base = pd.DataFrame(linhas)
    assert len(base) == 8073
    out = construir_t06(base)
    assert out["setores_integrados"].sum() == 8073
    assert out["setores_convergentes"].sum() == 30
    assert out["populacao_convergente"].sum() == 3000
