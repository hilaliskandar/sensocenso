from tic_tim_demografia.fontes.http import filtrar_links


def test_filtrar_links_por_tokens_e_extensao() -> None:
    links = [
        "https://exemplo/Agregados_por_setores_SP.csv",
        "https://exemplo/Agregados_por_setores_RJ.csv",
        "https://exemplo/Dicionario.xlsx",
    ]
    resultado = filtrar_links(links, conter=["setores", "sp"], terminar_com=[".csv"])
    assert resultado == ["https://exemplo/Agregados_por_setores_SP.csv"]


def test_filtrar_links_sem_filtro_preserva_ordem_deterministica() -> None:
    links = ["https://exemplo/b.csv", "https://exemplo/a.csv"]
    assert filtrar_links(links) == sorted(links)
