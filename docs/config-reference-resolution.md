# Resolução de referências de configuração

`monan_jedi_workflow.references.resolve_references()` resolve referências
internas explícitas após a composição de componentes e antes da preparação de
qualquer ciclo.

## Referências estáticas

Referências usam chaves separadas por ponto:

```yaml
installation:
  root: /p/projetos/monan/builds/monan-jedi-mpas
  bin_root: "{installation.root}/bin"

site:
  workspace: /p/projetos/monan/runs

run:
  tasks: 128
  partition: "{site.workspace}/meshes/graph.info.part.{tasks}"
```

Uma referência que ocupa toda a string preserva o tipo do valor de origem. Por
isso, `"{run.tasks}"` produz o inteiro `128`; já uma referência embutida em
texto é convertida em texto.

Os aliases `{tasks}` e `{experiment_name}` resolvem, respectivamente, para
`{run.tasks}` e `{experiment.name}`.

## Placeholders tardios do ciclo

Os placeholders abaixo não são resolvidos nesta etapa e são preservados para o
gerador de ciclos:

```text
{cycle_id}
{analysis_time}
{analysis_mpas_time}
{forecast_start_time}
{forecast_start_mpas_time}
{valid_time}
{valid_mpas_time}
{offset_hours}
{forecast_lead_hours}
```

## Restrições intencionais

O resolvedor é puro e não tem efeitos colaterais:

- não lê arquivos adicionais;
- não cria diretórios;
- não executa programas;
- não expande variáveis de ambiente nem `~`;
- interrompe com erro para referências inexistentes, circulares ou para mapas e
  listas inseridos dentro de texto.
