# Checklist de promoção — Caieiras APOND

O PR deve permanecer em rascunho enquanto qualquer item abaixo estiver pendente.

- [ ] `validar_config_entorno.py` retorna PASS.
- [ ] `agregar_entorno_apond.py` retorna PASS com 207 setores e 7 APONDs.
- [ ] QA de contadores confirma os 207 setores do recorte e os campos V050/V052/V054.
- [ ] `calcular_entorno_apond.py` retorna PASS com 30 distribuições por território.
- [ ] Fechamento do percentual bruto em 100% nos grupos com denominador observado positivo.
- [ ] Fechamento do percentual no domínio aplicável em 100% nos grupos com denominador aplicável positivo.
- [ ] Categorias fora do domínio permanecem sem percentual de domínio.
- [ ] Consolidado MUNICIPIO reconciliado pela soma dos contadores APOND.
- [ ] Entorno incorporado em nova base v2 sem alterar a base normalizada v1.
- [ ] Base territorial/cartografia de Caieiras validada.
- [ ] PDF piloto curto gerado e submetido a QA visual/estatístico.
- [ ] Somente após o piloto: builders dos Volumes I–III liberados para execução completa.
