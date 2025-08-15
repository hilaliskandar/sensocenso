"""
Funções para cálculo de indicadores demográficos a partir de dados do Censo 2022 em formato long (idade simples).
Baseado nas recomendações técnicas e operacionais fornecidas.
"""
import pandas as pd
import numpy as np

def calcular_populacoes_agrupadas(df, idade_col='idade', sexo_col='sexo', pop_col='pop'):
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

def gerar_flags_qualidade(grupos):
    """
    Gera flags de qualidade para os indicadores, conforme recomendações técnicas.
    """
    flags = {}
    flags['denominador_pequeno'] = grupos['pop_15_64'] < 500
    # Outras flags podem ser implementadas conforme necessidade (ex: age heaping)
    return flags

def calcular_indicadores_df(df, idade_col='idade', sexo_col='sexo', pop_col='pop', group_cols=['CodIBGE','Municipio']):
    """
    Calcula indicadores demográficos para cada município (ou grupo definido).
    Retorna DataFrame com indicadores e flags de qualidade.
    """
    results = []
    for keys, subdf in df.groupby(group_cols):
        grupos = calcular_populacoes_agrupadas(subdf, idade_col, sexo_col, pop_col)
        ind = calcular_indicadores_demograficos(grupos)
        flags = gerar_flags_qualidade(grupos)
        row = dict(zip(group_cols, keys if isinstance(keys, tuple) else [keys]))
        row.update(grupos)
        row.update(ind)
        row.update(flags)
        results.append(row)
    return pd.DataFrame(results)
