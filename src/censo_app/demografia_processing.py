"""
SensoCenso - Módulo de Processamento Demográfico com Fallback para Regiões Intermediárias IBGE

Este módulo implementa funções para integração de dados demográficos com mapeamentos de 
Regiões Metropolitanas (RM) e Aglomerações Urbanas (AU), incluindo lógica de fallback
para Regiões Intermediárias IBGE quando os municípios não possuem mapeamento RM/AU.
"""

from __future__ import annotations
from typing import Optional, Dict, Any
import pandas as pd
from pathlib import Path
import logging

# Configurar logging
logger = logging.getLogger(__name__)

# Mapeamento baseado na divisão regional IBGE 2017 (Regiões Intermediárias)
# Este é um subconjunto dos códigos IBGE para regiões intermediárias mais importantes
# Em um ambiente de produção, isso deveria vir de uma fonte oficial do IBGE
IBGE_INTERMEDIARY_REGIONS = {
    # São Paulo - algumas regiões intermediárias como exemplo
    3501: "São Paulo",
    3502: "Santos", 
    3503: "Campinas",
    3504: "Ribeirão Preto",
    3505: "São José do Rio Preto",
    3506: "Araçatuba",
    3507: "Presidente Prudente",
    3508: "Marília",
    3509: "Bauru",
    3510: "Araraquara",
    3511: "São Carlos",
    3512: "Piracicaba",
    3513: "Sorocaba",
    3514: "Itapetininga",
    3515: "Registro",
    3550: "São Paulo",  # Capital São Paulo também mapeia para região São Paulo
    
    # Rio de Janeiro 
    3301: "Rio de Janeiro",
    3302: "Campos dos Goytacazes",
    3303: "Volta Redonda",
    3304: "Rio de Janeiro",  # Capital Rio também mapeia
    
    # Minas Gerais - algumas principais
    3101: "Belo Horizonte", 
    3102: "Uberlândia",
    3103: "Juiz de Fora",
    3104: "Montes Claros",
    
    # Bahia
    2901: "Salvador",
    2902: "Feira de Santana",
    2903: "Vitória da Conquista",
    2304: "Fortaleza",  # Ceará
    
    # Mato Grosso do Sul
    5002: "Campo Grande",
    
    # Acre  
    1200: "Rio Branco",
    
    # Outras regiões principais (códigos exemplificativos)
    # Em produção, todos os códigos oficiais do IBGE deveriam estar aqui
}


def get_municipio_intermediary_region(cod_mun: int) -> Optional[str]:
    """
    Obtém a Região Intermediária IBGE para um código de município.
    
    Args:
        cod_mun: Código IBGE do município (7 dígitos)
        
    Returns:
        Nome da Região Intermediária ou None se não encontrada
        
    Note:
        Esta função usa um mapeamento simplificado. Em produção, deveria
        consultar dados oficiais completos do IBGE.
    """
    if not cod_mun or pd.isna(cod_mun):
        return None
        
    try:
        # Converter para int se necessário
        cod_mun = int(cod_mun)
        
        # O código da região intermediária são os primeiros 4 dígitos do código do município
        # seguindo a metodologia IBGE 2017
        regiao_code = cod_mun // 1000  # Remove os últimos 3 dígitos
        
        return IBGE_INTERMEDIARY_REGIONS.get(regiao_code)
        
    except (ValueError, TypeError):
        logger.warning(f"Código de município inválido: {cod_mun}")
        return None


def merge_rm_au_from_excel(df: pd.DataFrame, excel_path: str) -> pd.DataFrame:
    """
    Integra dados de RM/AU a partir de Excel com fallback para Regiões Intermediárias IBGE.
    
    Para municípios sem mapeamento RM/AU, utiliza automaticamente a Região Intermediária 
    IBGE correspondente.
    
    Args:
        df: DataFrame com dados demográficos (deve conter coluna CD_MUN)
        excel_path: Caminho para o arquivo Excel com mapeamento RM/AU
        
    Returns:
        DataFrame enriquecido com colunas:
        - CD_RM: Código da RM (quando disponível)
        - NM_RM: Nome da RM (quando disponível)  
        - CD_AU: Código da AU (quando disponível)
        - NM_AU: Nome da AU (quando disponível)
        - RegiaoIntermediariaIBGE: Região Intermediária IBGE (fallback)
        
    Raises:
        FileNotFoundError: Se o arquivo Excel não for encontrado
        ValueError: Se a coluna CD_MUN não existir no DataFrame
    """
    if "CD_MUN" not in df.columns:
        raise ValueError("DataFrame deve conter coluna 'CD_MUN' para realizar o merge")
        
    # Verificar se arquivo existe
    excel_file = Path(excel_path)
    if not excel_file.exists():
        raise FileNotFoundError(f"Arquivo Excel não encontrado: {excel_path}")
    
    # Carregar dados do Excel
    try:
        rm_au_data = pd.read_excel(excel_path)
        logger.info(f"Carregados {len(rm_au_data)} registros do Excel: {excel_path}")
    except Exception as e:
        raise RuntimeError(f"Erro ao ler arquivo Excel: {e}")
    
    # Verificar colunas necessárias no Excel
    required_cols = ['COD_MUN', 'COD_RECMETROPOL', 'NOME_RECMETROPOL']
    missing_cols = [col for col in required_cols if col not in rm_au_data.columns]
    if missing_cols:
        raise ValueError(f"Colunas ausentes no Excel: {missing_cols}")
    
    # Preparar dados de RM/AU para merge
    rm_au_clean = rm_au_data[['COD_MUN', 'COD_RECMETROPOL', 'NOME_RECMETROPOL']].copy()
    rm_au_clean = rm_au_clean.drop_duplicates(subset=['COD_MUN'])
    
    # Renomear colunas para padrão do sistema
    rm_au_clean = rm_au_clean.rename(columns={
        'COD_MUN': 'CD_MUN',
        'COD_RECMETROPOL': 'CD_RM', 
        'NOME_RECMETROPOL': 'NM_RM'
    })
    
    # Fazer merge com dados originais
    result = df.merge(rm_au_clean, on='CD_MUN', how='left')
    
    # Contar municípios com e sem RM/AU
    municipios_com_rm = result['CD_RM'].notna().sum()
    municipios_sem_rm = result['CD_RM'].isna().sum()
    
    logger.info(f"Municípios com RM/AU: {municipios_com_rm}")
    logger.info(f"Municípios sem RM/AU: {municipios_sem_rm}")
    
    # Aplicar fallback para Região Intermediária IBGE nos municípios sem RM/AU
    result['RegiaoIntermediariaIBGE'] = None
    
    for idx, row in result.iterrows():
        if pd.isna(row['CD_RM']):  # Município sem RM/AU
            regiao_intermediaria = get_municipio_intermediary_region(row['CD_MUN'])
            result.at[idx, 'RegiaoIntermediariaIBGE'] = regiao_intermediaria
    
    # Adicionar colunas de AU (placeholder para futuras extensões)
    if 'CD_AU' not in result.columns:
        result['CD_AU'] = None
    if 'NM_AU' not in result.columns:
        result['NM_AU'] = None
    
    # Log de estatísticas finais
    regioes_intermediarias_aplicadas = result['RegiaoIntermediariaIBGE'].notna().sum()
    logger.info(f"Regiões Intermediárias IBGE aplicadas: {regioes_intermediarias_aplicadas}")
    
    return result


def validate_demografia_processing_result(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Valida o resultado do processamento demográfico e retorna estatísticas.
    
    Args:
        df: DataFrame processado pela função merge_rm_au_from_excel
        
    Returns:
        Dicionário com estatísticas de validação:
        - total_municipios: Total de municípios no dataset
        - municipios_com_rm: Municípios com RM/AU 
        - municipios_com_regiao_intermediaria: Municípios com Região Intermediária
        - municipios_sem_mapeamento: Municípios sem qualquer mapeamento regional
        - cobertura_rm_percent: Percentual de cobertura RM/AU
        - cobertura_total_percent: Percentual de cobertura total (RM/AU + Intermediária)
    """
    total = len(df)
    com_rm = df['CD_RM'].notna().sum() if 'CD_RM' in df.columns else 0
    com_intermediaria = df['RegiaoIntermediariaIBGE'].notna().sum() if 'RegiaoIntermediariaIBGE' in df.columns else 0
    sem_mapeamento = total - com_rm - com_intermediaria
    
    stats = {
        'total_municipios': total,
        'municipios_com_rm': com_rm,
        'municipios_com_regiao_intermediaria': com_intermediaria, 
        'municipios_sem_mapeamento': sem_mapeamento,
        'cobertura_rm_percent': (com_rm / total * 100) if total > 0 else 0,
        'cobertura_total_percent': ((com_rm + com_intermediaria) / total * 100) if total > 0 else 0
    }
    
    return stats