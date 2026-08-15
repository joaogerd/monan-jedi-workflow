# Troubleshooting

## `cycle-doctor` diz que falta um YAML

O diretório passado como `CASE` precisa conter `jedi.yaml`, `mpas.yaml` e `obs2ioda.yaml` para a campanha completa.

Para testar somente o stage JEDI durante desenvolvimento:

```bash
monan-jedi-workflow cycle-doctor CASE --cycle TIME \
  --no-observations --no-forecast
```

## `simpleWorkflow` não aparece no doctor

Isso é aviso, não falha do domínio. Os comandos `monan-jedi-workflow ...` continuam funcionando manualmente. Instale `simpleWorkflow` quando quiser executar a DAG de pesquisa.

## Background não existe

Confira se o ciclo é o primeiro:

- primeiro ciclo: `background.initial_source`;
- demais: `background.source` deve resolver para o produto do forecast anterior.

Para 3D-FGAT, confira especialmente se o horário no nome do arquivo é o horário do **background**, não o horário da análise.

## JEDI PBS terminou mas `jedi-validate` falha

Veja:

```text
RUN/.monan-jedi-workflow/jedi-validation.json
```

Ele informa marcadores de log e outputs ausentes. Ajuste `validation` ao comportamento comprovado da versão atual; não enfraqueça a validação apenas para fazer o stage passar.

## Erro de malha/partição

Trate como um pacote coerente:

- background/análise;
- invariant/static mesh;
- `graph.info.part.N`;
- namelist;
- streams;
- número de ranks.

Não substitua um item isoladamente sem verificar compatibilidade.

## Tutorial antigo funciona diferente

Use o tutorial para identificar a função de uma etapa. Para nomes de executáveis, chaves YAML, arquivos de runtime e variáveis, use o baseline atual validado.
