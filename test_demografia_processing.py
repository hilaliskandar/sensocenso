"""
Testes unitários para o módulo de processamento demográfico.

Este módulo testa a funcionalidade de integração RM/AU com fallback para 
Regiões Intermediárias IBGE.
"""

import unittest
import pandas as pd
import tempfile
import os
from pathlib import Path

# Importar módulo a ser testado
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from censo_app.demografia_processing import (
    merge_rm_au_from_excel,
    get_municipio_intermediary_region,
    validate_demografia_processing_result
)


class TestDemografiaProcessing(unittest.TestCase):
    """Testes para funções de processamento demográfico."""
    
    def setUp(self):
        """Configurar dados de teste."""
        # Criar DataFrame de teste com municípios
        self.test_df = pd.DataFrame({
            'CD_MUN': [3550308, 3304557, 2304400, 1100205, 5002704, 1200013],  # SP, RJ, CE, RO, MT, AC
            'NM_MUN': ['São Paulo', 'Rio de Janeiro', 'Fortaleza', 'Porto Velho', 'Campo Grande', 'Acrelandia'],
            'populacao': [12000000, 6000000, 2600000, 500000, 900000, 15000]
        })
        
        # Criar dados de Excel de teste (apenas alguns municípios têm RM)
        self.rm_au_data = pd.DataFrame({
            'COD_MUN': [3550308, 3304557, 1100205],  # Apenas SP, RJ e Porto Velho têm RM
            'NOME_MUN': ['São Paulo', 'Rio de Janeiro', 'Porto Velho'],
            'COD_RECMETROPOL': [1, 2, 3],
            'NOME_RECMETROPOL': ['RM São Paulo', 'RM Rio de Janeiro', 'RM Porto Velho'],
            'COD_UF': [35, 33, 11],
            'SIGLA_UF': ['SP', 'RJ', 'RO']
        })
        
        # Criar arquivo Excel temporário
        self.temp_excel = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        self.rm_au_data.to_excel(self.temp_excel.name, index=False)
        self.temp_excel.close()
    
    def tearDown(self):
        """Limpar arquivos temporários."""
        if os.path.exists(self.temp_excel.name):
            os.unlink(self.temp_excel.name)
    
    def test_get_municipio_intermediary_region_valid_codes(self):
        """Testar obtenção de região intermediária para códigos válidos."""
        # São Paulo (código 3550308 -> região 3550)
        regiao = get_municipio_intermediary_region(3550308)
        self.assertEqual(regiao, "São Paulo")
        
        # Rio de Janeiro (código 3304557 -> região 3304 - agora mapeado)
        regiao = get_municipio_intermediary_region(3304557)
        self.assertEqual(regiao, "Rio de Janeiro")
        
        # Código que mapeia para região conhecida
        regiao = get_municipio_intermediary_region(3501000)  # região 3501
        self.assertEqual(regiao, "São Paulo")
    
    def test_get_municipio_intermediary_region_invalid_codes(self):
        """Testar comportamento com códigos inválidos."""
        self.assertIsNone(get_municipio_intermediary_region(None))
        self.assertIsNone(get_municipio_intermediary_region("invalid"))
        self.assertIsNone(get_municipio_intermediary_region(0))
    
    def test_merge_rm_au_from_excel_basic_functionality(self):
        """Testar funcionalidade básica de merge com RM/AU."""
        result = merge_rm_au_from_excel(self.test_df, self.temp_excel.name)
        
        # Verificar que todas as linhas originais estão presentes
        self.assertEqual(len(result), len(self.test_df))
        
        # Verificar colunas adicionadas
        expected_columns = ['CD_RM', 'NM_RM', 'CD_AU', 'NM_AU', 'RegiaoIntermediariaIBGE']
        for col in expected_columns:
            self.assertIn(col, result.columns)
    
    def test_merge_rm_au_municipios_com_rm_unchanged(self):
        """Testar que municípios com RM/AU mantêm seus dados."""
        result = merge_rm_au_from_excel(self.test_df, self.temp_excel.name)
        
        # São Paulo deve ter RM
        sp_row = result[result['CD_MUN'] == 3550308].iloc[0]
        self.assertEqual(sp_row['CD_RM'], 1)
        self.assertEqual(sp_row['NM_RM'], 'RM São Paulo')
        self.assertIsNone(sp_row['RegiaoIntermediariaIBGE'])  # Não deve ter fallback
        
        # Rio de Janeiro deve ter RM
        rj_row = result[result['CD_MUN'] == 3304557].iloc[0]
        self.assertEqual(rj_row['CD_RM'], 2)
        self.assertEqual(rj_row['NM_RM'], 'RM Rio de Janeiro')
        self.assertIsNone(rj_row['RegiaoIntermediariaIBGE'])  # Não deve ter fallback
    
    def test_merge_rm_au_municipios_sem_rm_recebem_fallback(self):
        """Testar que municípios sem RM/AU recebem Região Intermediária."""
        result = merge_rm_au_from_excel(self.test_df, self.temp_excel.name)
        
        # Fortaleza (CE) não tem RM, deve receber região intermediária (agora mapeada)
        ce_row = result[result['CD_MUN'] == 2304400].iloc[0]
        self.assertTrue(pd.isna(ce_row['CD_RM']))  # Não deve ter RM
        self.assertEqual(ce_row['RegiaoIntermediariaIBGE'], "Fortaleza")
        
        # Campo Grande (MT) - código 5002704 agora está mapeado
        mt_row = result[result['CD_MUN'] == 5002704].iloc[0]
        self.assertTrue(pd.isna(mt_row['CD_RM']))  # Não deve ter RM
        self.assertEqual(mt_row['RegiaoIntermediariaIBGE'], "Campo Grande")  # Agora mapeada
    
    def test_merge_rm_au_arquivo_inexistente(self):
        """Testar comportamento com arquivo Excel inexistente."""
        with self.assertRaises(FileNotFoundError):
            merge_rm_au_from_excel(self.test_df, "arquivo_inexistente.xlsx")
    
    def test_merge_rm_au_dataframe_sem_cd_mun(self):
        """Testar comportamento com DataFrame sem coluna CD_MUN."""
        df_invalid = pd.DataFrame({'outras_colunas': [1, 2, 3]})
        
        with self.assertRaises(ValueError) as context:
            merge_rm_au_from_excel(df_invalid, self.temp_excel.name)
        
        self.assertIn("CD_MUN", str(context.exception))
    
    def test_validate_demografia_processing_result(self):
        """Testar função de validação de resultados."""
        result = merge_rm_au_from_excel(self.test_df, self.temp_excel.name)
        stats = validate_demografia_processing_result(result)
        
        # Verificar estrutura das estatísticas
        expected_keys = [
            'total_municipios',
            'municipios_com_rm', 
            'municipios_com_regiao_intermediaria',
            'municipios_sem_mapeamento',
            'cobertura_rm_percent',
            'cobertura_total_percent'
        ]
        
        for key in expected_keys:
            self.assertIn(key, stats)
        
        # Verificar valores esperados
        self.assertEqual(stats['total_municipios'], 6)
        self.assertEqual(stats['municipios_com_rm'], 3)  # SP, RJ, Porto Velho
        # Agora Fortaleza, Campo Grande e Acrelandia têm região intermediária
        self.assertEqual(stats['municipios_com_regiao_intermediaria'], 3)  
        self.assertEqual(stats['municipios_sem_mapeamento'], 0)  # Todos cobertos
    
    def test_merge_rm_au_preserva_dados_originais(self):
        """Testar que dados originais do DataFrame são preservados."""
        result = merge_rm_au_from_excel(self.test_df, self.temp_excel.name)
        
        # Verificar que colunas originais estão preservadas
        for col in self.test_df.columns:
            self.assertIn(col, result.columns)
            
        # Verificar que valores originais estão corretos
        for idx, row in self.test_df.iterrows():
            result_row = result[result['CD_MUN'] == row['CD_MUN']].iloc[0]
            self.assertEqual(result_row['NM_MUN'], row['NM_MUN'])
            self.assertEqual(result_row['populacao'], row['populacao'])


class TestIntegracaoCompleta(unittest.TestCase):
    """Testes de integração com cenários mais complexos."""
    
    def test_cenario_municipio_com_regiao_intermediaria_mapeada(self):
        """Testar município que deveria receber região intermediária mapeada."""
        # Criar um município que mapeia para uma região conhecida
        df_test = pd.DataFrame({
            'CD_MUN': [3501608],  # Código que deveria mapear para região 3501 (São Paulo)
            'NM_MUN': ['Jundiaí'],
            'populacao': [400000]
        })
        
        # Excel sem este município (para forçar fallback)
        empty_excel_data = pd.DataFrame({
            'COD_MUN': [9999999],  # Município inexistente
            'NOME_MUN': ['Inexistente'],
            'COD_RECMETROPOL': [999],
            'NOME_RECMETROPOL': ['RM Inexistente'],
            'COD_UF': [99],
            'SIGLA_UF': ['XX']
        })
        
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
            empty_excel_data.to_excel(temp_file.name, index=False)
            temp_file.close()
            
            try:
                result = merge_rm_au_from_excel(df_test, temp_file.name)
                
                # Município deve estar sem RM
                row = result.iloc[0]
                self.assertTrue(pd.isna(row['CD_RM']))
                
                # Mas deve ter região intermediária
                self.assertEqual(row['RegiaoIntermediariaIBGE'], "São Paulo")
                
            finally:
                os.unlink(temp_file.name)


if __name__ == '__main__':
    # Configurar logging para os testes
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Executar testes
    unittest.main(verbosity=2)