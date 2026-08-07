"""
Funções para cálculo de indicadores demográficos a partir de dados do Censo 2022 em formato long (idade simples).
Baseado nas recomendações técnicas e operacionais fornecidas.
"""
import pandas as pd
import numpy as np

def calcular_populacoes_agrupadas(
    df: pd.DataFrame,
    idade_col: str = 'idade',
    sexo_col: str = 'sexo',
    pop_col: str = 'pop'
) -> dict[str, float]:
    """
    Agrega populações por faixas etárias e sexo, retornando um dicionário com os principais grupos.
    Espera DataFrame no formato long: CodIBGE, Municipio, sexo, idade, pop
    """
    grupos = {}
    df = df.copy()
    df[idade_col] = pd.to_numeric(df[idade_col], errors='coerce')
    grupos['pop_0_14'] = df[df[idade_col].between(0,14)][pop_col].sum()
    grupos['pop_15_64'] = df[df[idade_col].between(15,64)][pop_col].sum()
    grupos['pop_20_64'] = df[df[idade_col].between(20,64)][pop_col].sum()
    grupos['pop_60p'] = df[df[idade_col]>=60][pop_col].sum()
    grupos['pop_65p'] = df[df[idade_col]>=65][pop_col].sum()
    grupos['pop_80p'] = df[df[idade_col]>=80][pop_col].sum()
    grupos['pop_total'] = df[pop_col].sum()
    grupos['pop_idade0'] = df[df[idade_col]==0][pop_col].sum()
    return grupos

def calcular_indicadores_demograficos(grupos):
    """
    Calcula os principais indicadores demográficos a partir dos agregados populacionais.
    Retorna um dicionário com os indicadores.
    """
    ind = {}
    # Razões de dependência
    ind['RDT'] = ((grupos['pop_0_14'] + grupos['pop_65p']) / grupos['pop_15_64'] * 100) if grupos['pop_15_64'] else np.nan
    ind['RDJ'] = (grupos['pop_0_14'] / grupos['pop_15_64'] * 100) if grupos['pop_15_64'] else np.nan
    ind['RDI'] = (grupos['pop_65p'] / grupos['pop_15_64'] * 100) if grupos['pop_15_64'] else np.nan
    ind['OADR'] = (grupos['pop_65p'] / grupos['pop_20_64'] * 100) if grupos['pop_20_64'] else np.nan
    ind['PSR'] = (grupos['pop_20_64'] / grupos['pop_65p']) if grupos['pop_65p'] else np.nan
    # Envelhecimento
    ind['IE_60p'] = (grupos['pop_60p'] / grupos['pop_0_14'] * 100) if grupos['pop_0_14'] else np.nan
    ind['IE_65p'] = (grupos['pop_65p'] / grupos['pop_0_14'] * 100) if grupos['pop_0_14'] else np.nan
    ind['Prop_80p'] = (grupos['pop_80p'] / grupos['pop_total'] * 100) if grupos['pop_total'] else np.nan
    # Natalidade (proxy)
    ind['TBN_proxy'] = (grupos['pop_idade0'] / grupos['pop_total'] * 1000) if grupos['pop_total'] else np.nan
    return ind

def calcular_age_heaping_index(df: pd.DataFrame, idade_col: str = 'idade', pop_col: str = 'pop') -> float:
    """
    Calcula o Índice de Whipple (heaping em múltiplos de 5 e 10).
    Valores próximos de 100 indicam boa qualidade; muito acima ou abaixo sugerem
    concentração preferencial de idades declaradas.

    Retorna o índice de Whipple (%) ou NaN se dados insuficientes.
    """
    try:
        df = df.copy()
        df[idade_col] = pd.to_numeric(df[idade_col], errors='coerce')
        subset = df[df[idade_col].between(23, 62)]
        if subset.empty:
            return float('nan')
        pop_total = subset[pop_col].sum()
        if pop_total == 0:
            return float('nan')
        pop_5s = subset[subset[idade_col] % 5 == 0][pop_col].sum()
        whipple = (pop_5s / pop_total) * 500.0
        return round(float(whipple), 2)
    except Exception:
        return float('nan')


def gerar_flags_qualidade(grupos, whipple_index: float | None = None):
    """
    Gera flags de qualidade para os indicadores, conforme recomendações técnicas.

    Flags geradas:
    - denominador_pequeno: pop_15_64 < 500
    - idosos_dominantes: mais idosos (65+) que jovens (0-14), indicando envelhecimento avançado
    - alta_prop_80p: proporção de 80+ acima de 5% da população total
    - age_heaping: Índice de Whipple fora da faixa [105, 174] (qualidade moderada ou ruim)
    - zero_total: população total é zero (dados ausentes ou inválidos)
    - tbn_proxy_suspeita: proxy de natalidade muito baixo (< 5‰) ou muito alto (> 35‰)
    """
    flags: dict = {}
    flags['denominador_pequeno'] = grupos.get('pop_15_64', 0) < 500
    flags['zero_total'] = grupos.get('pop_total', 0) == 0

    pop_total = grupos.get('pop_total', 0)
    pop_0_14 = grupos.get('pop_0_14', 0)
    pop_65p = grupos.get('pop_65p', 0)
    pop_80p = grupos.get('pop_80p', 0)

    # Envelhecimento avançado: mais idosos 65+ do que crianças 0-14
    flags['idosos_dominantes'] = (pop_0_14 > 0) and (pop_65p > pop_0_14)

    # Alta proporção de 80+ (acima de 5%)
    if pop_total > 0:
        flags['alta_prop_80p'] = (pop_80p / pop_total * 100) > 5.0
    else:
        flags['alta_prop_80p'] = False

    # Índice de Whipple (age heaping) — qualidade moderada: 105–174; ruim: > 174
    if whipple_index is not None and not np.isnan(whipple_index):
        flags['age_heaping'] = whipple_index > 174.0
        flags['age_heaping_moderado'] = 105.0 < whipple_index <= 174.0
    else:
        flags['age_heaping'] = False
        flags['age_heaping_moderado'] = False

    # Proxy TBN suspeita (< 5‰ ou > 35‰)
    pop_idade0 = grupos.get('pop_idade0', 0)
    if pop_total > 0:
        tbn = pop_idade0 / pop_total * 1000
        flags['tbn_proxy_suspeita'] = tbn < 5.0 or tbn > 35.0
    else:
        flags['tbn_proxy_suspeita'] = False

    return flags

def calcular_indicadores_df(df, idade_col='idade', sexo_col='sexo', pop_col='pop', group_cols=None):
    """
    Calcula indicadores demográficos para cada município (ou grupo definido).
    Retorna DataFrame com indicadores e flags de qualidade.
    """
    if group_cols is None:
        group_cols = ['CodIBGE', 'Municipio']
    results = []
    for keys, subdf in df.groupby(group_cols):
        grupos = calcular_populacoes_agrupadas(subdf, idade_col, sexo_col, pop_col)
        ind = calcular_indicadores_demograficos(grupos)
        whipple = calcular_age_heaping_index(subdf, idade_col, pop_col)
        ind['whipple_index'] = whipple
        flags = gerar_flags_qualidade(grupos, whipple_index=whipple)
        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else [keys]))
        row.update(grupos)
        row.update(ind)
        row.update(flags)
        results.append(row)
    return pd.DataFrame(results)
