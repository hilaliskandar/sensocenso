# Plano de teste de portabilidade — RMRP

O Alê 2.0 fornecerá uma configuração `municipios.yml` gerada a partir de seu contrato territorial canônico da Região Metropolitana de Ribeirão Preto.

Escopo inicial deste branch:

1. aceitar grupos territoriais genéricos sem quebrar a configuração TIC-TIM;
2. executar etapa 00 para um universo que não utiliza as categorias `interna`/`externa`;
3. preservar a compatibilidade dos produtos TIC-TIM por meio do alias legado `Municipio.coroa`;
4. não generalizar silenciosamente as etapas analíticas posteriores que ainda usam a variável `coroa` em produtos e tabelas.

O teste de integração externo deverá avançar por gates separados: 00, 01 e 02a primeiro; 02b/02c somente após esses gates passarem para os 34 municípios da RMRP.
