from pathlib import Path

import pandas as pd
from PIL import Image

from tic_tim_demografia.etapa11e_manifesto_visual import (
    _validar_csv,
    _validar_png,
    inventario_visual,
)


def test_inventario_visual_tem_25_ids_unicos_e_um_externo():
    inv = inventario_visual()
    ids = [e.id for e in inv]
    assert len(inv) == 25
    assert len(set(ids)) == 25
    assert {e.id for e in inv if e.externo} == {"Q01"}
    assert len([e for e in inv if not e.externo]) == 24
    assert "M09" in ids
    assert "M12" in ids
    assert "T10" in ids


def test_inventario_nao_reintroduz_contagens_obsoletas():
    texto = " ".join(e.nota for e in inventario_visual())
    assert "987" not in texto
    assert "800" not in texto
    assert "1.255" in texto
    assert "959" in texto


def test_validar_png_exige_imagem_legivel_e_dimensao_minima(tmp_path: Path):
    path = tmp_path / "mapa.png"
    Image.new("RGB", (1200, 700), "white").save(path)
    qa = _validar_png(path)
    assert qa == {"largura_px": 1200, "altura_px": 700}


def test_validar_csv_exige_cabecalho_e_dados(tmp_path: Path):
    path = tmp_path / "dados.csv"
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(path, index=False)
    qa = _validar_csv(path)
    assert qa == {"linhas_dados": 2, "colunas": 2}
