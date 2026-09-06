# Estado — Caieiras — Cadernos APOND

Data: 2026-09-05

Estado corrente: `PIPELINE_ENTORNO_CODIFICADO_PENDENTE_EXECUCAO`.

## Fechado

- Gate territorial: 7 APONDs e 207 setores reconciliados.
- Normalização das 168 variáveis: QA interno concluído.
- Pipeline do Entorno codificado em duas camadas:
  1. agregação dos contadores setoriais por APOND;
  2. cálculo das 30 distribuições E01–E10 × três universos, com percentual bruto e percentual no domínio aplicável.
- Regras semânticas E01–E10 registradas declarativamente.

## Pendente para promover o gate

Executar sobre o `SP_setores_CD2022.dbf` canônico e exigir `PASS` nos dois QAs. Não considerar a presença do código como evidência de execução.

Após `PASS`:

1. incorporar o Entorno validado em nova base estatística v2, preservando a v1;
2. construir/validar a base territorial e a cartografia de Caieiras;
3. parametrizar e testar os builders para bloco único A01–A07;
4. produzir PDF piloto curto e executar QA visual/estatístico;
5. somente depois gerar os Volumes I–III completos.

Nenhum valor numérico de Entorno de Caieiras foi produzido ou inferido nesta branch enquanto o runtime permaneceu indisponível.
