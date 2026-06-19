# Doctor do ciclo de assimilação

O comando `monan-jedi-cycle-doctor` verifica se os recursos declarados para um
experimento cíclico estão disponíveis antes da geração do runtime, da
renderização de YAML/PBS ou da submissão de qualquer job.

Ele é estritamente de leitura: não cria arquivos, diretórios ou links; não
renderiza entradas MPAS/JEDI/PBS; não executa MPAS ou MPAS-JEDI; e não chama
`qsub`.

## Uso

A partir de um ambiente no qual o pacote esteja instalado, ou com o repositório
no `PYTHONPATH`:

```bash
python scripts/monan-jedi-cycle-doctor \
  configs/experiments/meu_experimento.yaml
```

O comando retorna:

- `0` quando todos os recursos satisfazem suas verificações;
- `1` quando pelo menos uma verificação falha;
- erro de configuração quando o YAML não tem a estrutura declarativa esperada.

## Configuração declarativa

Adicione uma seção `doctor` ao YAML do experimento. Cada entrada em `checks`
tem `name`, `path` e `kind` obrigatórios.

```yaml
experiment:
  name: cycle_1day_3dfgat_x1.10242

run:
  tasks: 64

doctor:
  checks:
    - name: executável MPAS-JEDI
      path: /p/projetos/monan_das/USUARIO/builds/monan-jedi/bin/mpasjedi_variational.x
      kind: executable
      access: [read, execute]

    - name: matriz de covariância de erros de background
      path: /p/projetos/monan_das/USUARIO/data/bmatrix/mpasstatic.nc
      kind: file
      access: [read]

    - name: metadados da matriz B
      path: /p/projetos/monan_das/USUARIO/data/bmatrix/mpasstatic_metadata.nc
      kind: file
      access: [read]

    - name: invariante da geometria
      path: /p/projetos/monan_das/USUARIO/data/mesh/x1.10242.invariant.nc
      kind: file
      access: [read]

    - name: partição compatível com run.tasks
      path: /p/projetos/monan_das/USUARIO/data/mesh/x1.10242.graph.info.part.{tasks}
      kind: file
      access: [read]

    - name: diretório de física
      path: /p/projetos/monan_das/USUARIO/data/physics
      kind: directory
      access: [read, execute]

    - name: diretório de runtime futuro
      path: /p/projetos/monan_das/USUARIO/runs/{experiment_name}
      kind: directory
      access: [read, write, execute]
```

A expansão de `{tasks}` obriga o `doctor` a procurar a partição correspondente
ao valor declarado em `run.tasks`. Por exemplo, `run.tasks: 64` exige o arquivo
`x1.10242.graph.info.part.64`; a presença isolada de uma partição `.part.32`
ou `.part.128` não aprova o experimento.

Os caminhos são avaliados como absolutos quando começam com `/`. Caminhos
relativos são interpretados em relação ao diretório do YAML. O caractere `~`
é expandido para o diretório inicial do usuário. Variáveis de ambiente não são
expandidas pelo `doctor`; use o caminho efetivo ou gere o YAML em uma etapa
anterior que já faça essa expansão.

Os valores possíveis para `kind` são:

- `file`: exige um arquivo regular;
- `directory`: exige um diretório;
- `executable`: exige um arquivo regular com permissão de execução para o
  usuário atual.

`access` é opcional e aceita uma lista sem repetições formada por `read`,
`write` e `execute`. Ela permite verificar as permissões necessárias sem
modificar o recurso.

## Estados temporais de FGAT

Uma verificação com `scope: trajectory` é expandida para cada estado previsto
pelo mesmo contrato temporal usado pelo planejador de ciclo. Portanto, o YAML
precisa conter `cycle`, `assimilation.method: 3dvar_fgat` e
`assimilation.fgat.trajectory_offsets_hours`.

```yaml
cycle:
  start: 2018-04-15T00:00:00Z
  end: 2018-04-16T00:00:00Z
  interval_hours: 6

assimilation:
  method: 3dvar_fgat
  fgat:
    trajectory_offsets_hours: [-3, 0, 3]

doctor:
  checks:
    - name: estados da trajetória FGAT
      path: /p/projetos/monan_das/USUARIO/states/{cycle_id}/x1.10242.init.{valid_mpas_time}.nc
      kind: file
      scope: trajectory
      access: [read]
```

Os placeholders globais abaixo estão disponíveis em qualquer `scope`, quando
os campos correspondentes existem no YAML:

```text
{experiment_name}
{tasks}
```

Os placeholders adicionais disponíveis para `scope: cycle` são:

```text
{cycle_id}
{analysis_time}
{analysis_mpas_time}
{forecast_start_time}
{forecast_start_mpas_time}
```

Em `scope: trajectory`, também podem ser usados:

```text
{valid_time}
{valid_mpas_time}
{offset_hours}
{forecast_lead_hours}
```

O `scope` padrão é `once`. Nesse modo os placeholders globais podem ser usados,
mas placeholders temporais não estão disponíveis.

## Critérios de aceite local

A implementação é aceita localmente quando os testes abaixo passam:

```bash
python -m pytest tests/test_doctor.py
python -m pytest
```

A suíte específica cobre: arquivo existente e ausente, diretório, executável
presente e ausente, permissões declaradas, partição vinculada a `run.tasks`,
expansão de estados FGAT, YAML inválido, placeholder inválido, ausência de
modificações no filesystem e integração da CLI com recursos temporários.

A validação com caminhos reais no JACI é deliberadamente posterior a esses
testes locais.
