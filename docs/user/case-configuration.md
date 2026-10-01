# Configuração de um caso cíclico

O caso separa três domínios e a orquestração:

```text
jedi.yaml       análise MPAS-JEDI
mpas.yaml       MONAN/MPAS e previsão que produz o próximo background
obs2ioda.yaml   seleção/preparação das observações
workflow.yaml   dependências e período (simpleWorkflow)
```

## O que o usuário deve configurar conscientemente

O workflow automatiza a mecânica do ciclo, mas não escolhe a ciência pelo
usuário. Antes da primeira campanha, revise explicitamente:

**MONAN/MPAS (`mpas.yaml` e templates referenciados)**

- malha/resolução e níveis verticais;
- condição inicial e arquivos estáticos;
- timestep e duração da integração;
- namelist, streams e configuração física;
- frequência e nomes dos estados que alimentam o FGAT e o próximo ciclo;
- recursos PBS necessários para essa configuração.

**Observações (`obs2ioda.yaml`)**

- quais famílias de observações entram no experimento;
- origem dos dados para todos os ciclos do período;
- conversores Obs2IODA e coleções IODA produzidas;
- horários/janelas e validações de cada produto;
- dependências adicionais, por exemplo GNSSRO quando sua aquisição for
  independente do PREPBUFR convencional.

**MPAS-JEDI (`jedi.yaml` e YAML variacional referenciado)**

- método de assimilação (no baseline atual, 3DVar/FGAT);
- geometria e variáveis de estado/controle;
- background e trajetória FGAT;
- matriz B e sua compatibilidade com a geometria;
- observadores, operadores, QC e erros de observação;
- janela de assimilação;
- minimização e saídas da análise.

**Campanha (`campaign.yaml`)**

- data inicial;
- duração (`P3D`, `P7D`, `P30D`, `P365D`);
- diretório/nome do experimento;
- se haverá forecast a partir da última análise.

A regra de arquitetura é: se uma mudança altera a ciência de um único ciclo,
ela pertence ao caso MONAN/observações/JEDI. Se apenas amplia quantas vezes o
mesmo ciclo validado será executado, ela pertence à campanha.

## Âncoras compartilhadas de runtime

Os casos JACI mantidos usam somente as duas interfaces públicas do ecossistema:

```bash
export MONAN_JEDI_INSTALL_ROOT=/p/projetos/monan_das/$USER/build/monan-jedi
export STACK_ROOT=/path/to/validated/spack-stack
```

Nos stages, a ligação fica explícita em `variables:`:

```yaml
variables:
  monan_jedi_install_root: ${MONAN_JEDI_INSTALL_ROOT}
  stack_root: ${STACK_ROOT}
```

Somente valores declarados em `variables:` recebem expansão de ambiente. Essa
regra é intencional: strings de runtime que pertencem ao Shell/PBS, como
`${PBS_JOBID}`, não devem ser consumidas prematuramente pelo Python. Uma
referência declarada em `variables:` que não esteja definida é erro de
configuração.

As duas âncoras não são suficientes sozinhas: o diretório apontado por
`MONAN_JEDI_INSTALL_ROOT` deve conter o contrato instalado:

```text
share/monan-jedi/install-manifest.json
```

com `ecosystem_contract_version: 2`. O workflow lê desse manifesto
`env_name`, `env_module`, `site_setup` e o layout da árvore de módulos.
Casos mantidos não usam defaults JACI copiados localmente quando esse manifesto
está ausente ou inválido.

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

### Validação científica dos produtos NetCDF

`required_outputs` garante apenas que o arquivo existe e não está vazio. Para
um produto que alimentará outro stage, `mpas.validation.netcdf` pode declarar
também o contrato estrutural/científico:

```yaml
validation:
  log: log.atmosphere.0000.out
  required_log_markers: ["Finished running the atmosphere core"]
  required_outputs:
    - "mpasout.{mpas_valid_file_time}.nc"
  netcdf:
    - path: "mpasout.{mpas_valid_file_time}.nc"
      consumer: "next MPAS-JEDI cycle"
      required_variables: [xtime]
      required_dimensions:
        Time: 1
        nCells: null
      time_variable: xtime
      expected_time: "{mpas_valid_time}"
```

`required_dimensions` aceita um tamanho exato ou `null` para exigir apenas a
presença. `required_global_attributes` funciona da mesma forma: uma string
exige valor exato e `null` exige apenas o atributo. `expected_time` é
renderizado com o contexto normal do ciclo; para MPAS, `xtime` em caracteres é
tratado como timestamp MPAS mesmo quando possui um atributo informativo
`units`.

Use esse contrato para propriedades que o consumidor realmente exige. Não
duplique no YAML detalhes internos que não fazem parte da interface científica.
A validação ocorre em `mpas-validate`, depois do término do scheduler e antes
de o produto ser aceito como válido para o próximo stage.

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


## Ambiente PBS

Os stages JEDI e MPAS aceitam `pbs.bootstrap` como lista ordenada de comandos
Shell executados no nó de computação antes das variáveis específicas do job e do
`mpiexec`. Use esse bloco para reconstruir o Spack-Stack selecionado por
`STACK_ROOT`.

`pbs.setup`, quando presente, continua aceito para compatibilidade com casos que
fazem `source` de um script local. Os exemplos mantidos não dependem mais de
scripts internos de outro repositório para preparar o ambiente científico.


For JACI, do not assume that custom environment variables exported in the login shell
are inherited by PBS. Cycle-aware stages render resolved paths directly into their
commands. The retained static baseline uses `pbs.environment_anchors` to embed the
two shared runtime anchors in the generated script.

When a bootstrap sources the JACI spack-stack `setup.sh` under `set -u`, protect
that source operation with a temporary `set +u` and restore the prior nounset state
afterward, as shown by the maintained examples.


### Static baseline runtime support

The maintained `3dfgat_mpastatic_x1.10242_2018041500` experiment does not
read files from a MONAN-JEDI source checkout. Stream lists, `geovars.yaml`,
`keptvars.yaml`, `obsop_name_map.yaml` and MPAS physics tables are resolved
below `${MONAN_JEDI_INSTALL_ROOT}/share`.

Date-specific observations are **scientific case data**, not software runtime.
The three 2018 UFO observation files, background states, invariant and mesh
partition therefore remain rooted in the experiment's configured
`paths.data_root`. This is the same ownership boundary used by the rest of the
ecosystem.
