# Configuração de um caso cíclico

O caso separa três domínios e a orquestração:

```text
jedi.yaml       análise MPAS-JEDI
mpas.yaml       previsão que produz o próximo background
obs2ioda.yaml   preparação das observações
workflow.yaml   dependências e período (simpleWorkflow)
```

## `jedi.yaml`

Contém o contrato da análise: horários, runtime, background, links, templates, PBS e validação.

Parâmetros temporais principais:

```yaml
cycle:
  step_hours: 6
  background_offset_hours: -3
  window_hours: 6
  first_cycle: "2018-04-15T00:00:00Z"
```

No caso de referência:

```text
analysis 00Z
background 21Z (dia anterior)
next analysis 06Z
next background 03Z
```

O primeiro ciclo usa:

```yaml
background:
  initial_source: /path/to/initial-background.nc
```

Os demais usam `background.source`, que normalmente aponta para o forecast do ciclo anterior.

Placeholders úteis incluem:

```text
{analysis_time}
{analysis_yyyymmddhh}
{analysis_mpas_file_time}
{background_time}
{background_mpas_file_time}
{previous_cycle_id}
{next_cycle_id}
{next_background_time}
{window_begin_time}
{window_end_time}
{window_length}
```

## `mpas.yaml`

Define como uma análise já validada inicializa o MPAS e qual produto do forecast será considerado background válido para o ciclo seguinte.

`lead_hours` controla o tempo utilizado pelo template MPAS e os placeholders `valid_*`. Ajuste-o ao caso atual validado. Não suponha que a duração de forecast de um tutorial antigo é correta para a instalação atual.

## `obs2ioda.yaml`

Define conversores, inputs, outputs e validação das coleções IODA.

Perfis existentes:

```text
examples/obs2ioda/prepbufr-tutorial/
examples/obs2ioda/prepbufr-operational/
examples/obs2ioda/sondes/
```

Use o perfil que corresponda ao conjunto de dados. A lista de coleções produzidas pode variar entre PREPBUFRs.

## `workflow.yaml`

Deve conter somente orquestração:

- período;
- tarefas;
- `depends_on`;
- comandos de domínio.

Não coloque nele aritmética científica de horários, regras de malha ou manipulação interna do runtime.

## Regra prática

Se uma informação seria necessária para executar uma etapa manualmente sem `simpleWorkflow`, ela pertence ao stage/configuração de domínio. Se ela apenas decide **quando** uma etapa roda, pertence ao orquestrador.

# JACI PBS node exclusivity

As of 20 August 2026, jobs submitted to JACI compute-node queues must request
exclusive node placement:

```text
#PBS -l place=excl
```

The `aux` queue is exempt because it permits shared resources. The workflow
adds this directive automatically according to the configured PBS queue, so
case YAML files do not need to declare `place: excl` themselves.
