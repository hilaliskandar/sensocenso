import pandas as pd

from tic_tim_demografia.etapa07 import _combinar_familias, _flag_limiar, _ou_triestado, _vetor_familias
from tic_tim_demografia.etapa08 import _vetor


def test_flag_limiar_zero_exige_valor_positivo():
    serie = pd.Series([0.0, 0.1, pd.NA], dtype="Float64")
    obtido = _flag_limiar(serie, 0.0, zero_estrito=True)
    assert obtido.tolist() == [0, 1, pd.NA]


def test_ou_triestado_preserva_incerteza():
    flags = pd.DataFrame(
        {
            "a": pd.Series([1, 0, 0, pd.NA], dtype="Int64"),
            "b": pd.Series([pd.NA, 0, pd.NA, pd.NA], dtype="Int64"),
        }
    )
    obtido = _ou_triestado(flags)
    assert obtido.iloc[0] == 1
    assert obtido.iloc[1] == 0
    assert pd.isna(obtido.iloc[2])
    assert pd.isna(obtido.iloc[3])


def test_convergencia_triestado_tres_de_quatro():
    flags = pd.DataFrame(
        {
            "F1": pd.Series([1, 1, 0, 1], dtype="Int64"),
            "F2": pd.Series([1, 0, 0, 1], dtype="Int64"),
            "F3": pd.Series([1, pd.NA, pd.NA, pd.NA], dtype="Int64"),
            "F4": pd.Series([0, 0, 0, pd.NA], dtype="Int64"),
        }
    )
    obtido = _combinar_familias(flags, 3)["CONVERGENCIA_3_OU_4"]
    assert obtido.iloc[0] == 1
    assert obtido.iloc[1] == 0
    assert obtido.iloc[2] == 0
    assert pd.isna(obtido.iloc[3])


def test_vetores_aceitam_valores_ausentes():
    linha75 = pd.Series({"F1": 1, "F2": pd.NA, "F3": 0, "F4": 1})
    linha80 = pd.Series({"F1_P80": 1, "F2_P80": pd.NA, "F3_P80": 0, "F4_P80": 1})
    assert _vetor_familias(linha75, ["F1", "F2", "F3", "F4"]) == "F1+F4"
    assert _vetor(linha80, ["F1_P80", "F2_P80", "F3_P80", "F4_P80"]) == "F1_P80+F4_P80"
