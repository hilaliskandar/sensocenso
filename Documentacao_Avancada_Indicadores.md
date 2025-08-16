# Documentação Avançada - Indicadores Demográficos com Fallback Regional

## Processamento Demográfico com Regiões Intermediárias IBGE

### Visão Geral

O módulo `demografia_processing.py` implementa funcionalidade avançada para integração de dados demográficos com mapeamentos regionais, incluindo lógica de fallback para Regiões Intermediárias IBGE quando municípios não possuem mapeamento para Regiões Metropolitanas (RM) ou Aglomerações Urbanas (AU).

### Funcionalidade Principal

#### `merge_rm_au_from_excel(df, excel_path)`

Esta função integra dados de RM/AU a partir de arquivo Excel com fallback automático para Regiões Intermediárias IBGE.

**Parâmetros:**
- `df`: DataFrame com dados demográficos (deve conter coluna `CD_MUN`)
- `excel_path`: Caminho para arquivo Excel com mapeamento RM/AU

**Retorna:**
DataFrame enriquecido com colunas:
- `CD_RM`: Código da Região Metropolitana (quando disponível)
- `NM_RM`: Nome da Região Metropolitana (quando disponível)  
- `CD_AU`: Código da Aglomeração Urbana (quando disponível)
- `NM_AU`: Nome da Aglomeração Urbana (quando disponível)
- `RegiaoIntermediariaIBGE`: Região Intermediária IBGE (fallback para municípios sem RM/AU)

### Lógica de Fallback

1. **Primeiro**: Tenta encontrar o município no mapeamento RM/AU do Excel
2. **Se encontrado**: Aplica dados de RM/AU e não aplica fallback
3. **Se NÃO encontrado**: Aplica automaticamente a Região Intermediária IBGE baseada no código do município

### Exemplo de Uso

```python
from censo_app.demografia_processing import merge_rm_au_from_excel
import pandas as pd

# Criar DataFrame com municípios
df_municipios = pd.DataFrame({
    'CD_MUN': [3550308, 5002704, 2304400],
    'NM_MUN': ['São Paulo', 'Campo Grande', 'Fortaleza'],
    'populacao': [12000000, 900000, 2600000]
})

# Aplicar merge com fallback
resultado = merge_rm_au_from_excel(
    df_municipios, 
    'insumos/Composicao_RM_2024.xlsx'
)

print(resultado[['NM_MUN', 'NM_RM', 'RegiaoIntermediariaIBGE']])
```

**Resultado esperado:**
```
        NM_MUN                    NM_RM RegiaoIntermediariaIBGE
0    São Paulo  RM de São Paulo               None
1 Campo Grande              NaN        Campo Grande  
2    Fortaleza   RM de Fortaleza              None
```

### Cobertura Regional

O sistema garante máxima cobertura regional através de:

1. **Cobertura RM/AU**: ~1.400 municípios cobertos por RMs e AUs oficiais
2. **Cobertura Intermediária**: Fallback para demais municípios usando divisão IBGE 2017
3. **Cobertura Total**: Próxima a 100% dos municípios brasileiros

### Validação de Resultados

Use `validate_demografia_processing_result()` para obter estatísticas:

```python
from censo_app.demografia_processing import validate_demografia_processing_result

stats = validate_demografia_processing_result(resultado)
print(f"Cobertura total: {stats['cobertura_total_percent']:.1f}%")
print(f"Municípios com RM/AU: {stats['municipios_com_rm']}")
print(f"Municípios com fallback: {stats['municipios_com_regiao_intermediaria']}")
```

### Divisão Regional IBGE 2017

As Regiões Intermediárias IBGE seguem a divisão territorial oficial estabelecida em 2017, substituindo as antigas mesorregiões. Cada município brasileiro pertence a uma região intermediária, identificada pelos primeiros 4 dígitos do código IBGE.

**Exemplos de códigos:**
- `3550308` (São Paulo-SP) → Região `3550` → "São Paulo"
- `5002704` (Campo Grande-MS) → Região `5002` → "Campo Grande"
- `2304400` (Fortaleza-CE) → Região `2304` → "Fortaleza"

### Estrutura do Excel RM/AU

O arquivo Excel deve conter as colunas:
- `COD_MUN`: Código IBGE do município (7 dígitos)
- `NOME_MUN`: Nome do município
- `COD_RECMETROPOL`: Código da Região Metropolitana
- `NOME_RECMETROPOL`: Nome da Região Metropolitana

### Casos de Uso

#### 1. Análise Demográfica Regional
```python
# Calcular indicadores por região
resultado_agrupado = resultado.groupby('NM_RM').agg({
    'populacao': 'sum',
    'CD_MUN': 'count'
}).rename(columns={'CD_MUN': 'num_municipios'})
```

#### 2. Mapeamento de Cobertura
```python
# Identificar municípios por tipo de mapeamento
com_rm = resultado[resultado['CD_RM'].notna()]
com_fallback = resultado[resultado['RegiaoIntermediariaIBGE'].notna()]
```

#### 3. Análise de Políticas Públicas
```python
# Comparar indicadores entre RMs e regiões intermediárias
rm_stats = com_rm.groupby('NM_RM')['indicador_demografico'].mean()
intermediaria_stats = com_fallback.groupby('RegiaoIntermediariaIBGE')['indicador_demografico'].mean()
```

### Notas Técnicas

1. **Performance**: O mapeamento é otimizado para grandes volumes de dados
2. **Flexibilidade**: Aceita diferentes formatos de arquivo Excel
3. **Robustez**: Trata erros de formato e dados ausentes
4. **Logging**: Registra estatísticas de processamento para auditoria
5. **Validação**: Verificações automáticas de integridade dos dados

### Limitações e Extensões Futuras

**Limitações atuais:**
- Mapeamento de Regiões Intermediárias é parcial (deve ser expandido com dados oficiais completos)
- Aglomerações Urbanas (AU) são placeholder para implementação futura
- Dependência de arquivo Excel específico

**Extensões planejadas:**
- Integração com APIs do IBGE para dados sempre atualizados
- Suporte a múltiplos formatos de entrada (CSV, JSON, bancos de dados)
- Cache inteligente para otimização de performance
- Validação automática contra dados oficiais IBGE

### Referências

- IBGE. Divisão Regional do Brasil em Regiões Geográficas Intermediárias e Imediatas 2017
- IBGE. Arranjos Populacionais e Concentrações Urbanas do Brasil 2015  
- Lei Complementar nº 14/1973 (criação de Regiões Metropolitanas)
- Constituição Federal de 1988, artigo 25, § 3º

---

*Para suporte técnico ou dúvidas sobre implementação, consulte os testes unitários em `test_demografia_processing.py` ou a documentação do código fonte.*