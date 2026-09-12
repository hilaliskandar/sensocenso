# Portabilidade territorial — contrato mínimo

## Objetivo

Permitir que as etapas iniciais do pipeline sejam executadas para universos territoriais distintos do TIC-TIM sem atribuir artificialmente a eles a semântica de `coroa interna/externa`.

## Compatibilidade

O contrato original permanece válido:

```yaml
- codigo_ibge: "..."
  nome: "..."
  coroa: "interna"
```

O novo contrato também aceita:

```yaml
- codigo_ibge: "..."
  nome: "..."
  grupo_territorial: "subregiao_1"
```

Em código, `Municipio.grupo_territorial` passa a ser o atributo canônico e `Municipio.coroa` é mantido como alias legado. Assim, a configuração TIC-TIM existente continua funcional sem alteração.

## Validação

Para configurações genéricas, `validacao.grupos_esperados` declara as cardinalidades esperadas por grupo. Se esse campo não existir, permanecem válidas as regras legadas `quantidade_coroa_interna` e `quantidade_coroa_externa`.

## Escopo desta mudança

A mudança pretende suportar os gates iniciais de portabilidade territorial, sobretudo etapas 00, 01 e 02a. Etapas analíticas posteriores ainda podem produzir campos e produtos explicitamente denominados `coroa`; sua generalização deve ser tratada em gates separados, sem reinterpretar silenciosamente grupos regionais como coroas TIC-TIM.
