# Inventário do baseline 3DVar-FGAT + MPASstatic

## Propósito

Este documento congela a classificação do caso validado
`3dfgat_mpastatic_x1.10242_2018041500` antes da migração para a arquitetura de
componentes do ciclo de assimilação.

O caso atual é a referência de regressão. Nenhum arquivo será removido ou
movido sem que o renderer novo produza uma configuração semanticamente
equivalente para esse baseline.

## Estado atual

O baseline é composto por seis arquivos obrigatórios:

```text
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/
  experiment.yaml
  runtime.yaml
  variables.yaml
  observations.yaml
  pbs.yaml
  validation.yaml
```

O carregador atual resolve seletor de variáveis e seletor de observações antes
da validação e do rendering. Esse comportamento deve ser preservado.

## Classificação de `experiment.yaml`

| Campo atual | Papel | Destino proposto | Observação |
|---|---|---|---|
| `experiment.name` | identificação | experimento mínimo | permanece no experimento |
| `experiment.description`, `stage` | metadados | experimento mínimo | permanece no experimento |
| `cycle.id` | identificação de instância | runtime renderizado | deve ser derivado de `cycle.start` no modo cíclico |
| `cycle.analysis_datetime` | tempo de análise | experimento mínimo / timeline | no baseline de passo único continua explícito; no ciclo é calculado |
| `cycle.background_datetime` | tempo do background | background | calculado pela estratégia de background e janela FGAT |
| `cycle.window_begin`, `window_length` | janela de AD | assimilação/FGAT | pertencem ao método e aos overrides do experimento |
| `cycle.mpas_background_file_date` | convenção de arquivo | background | deve ser renderizado a partir do tempo do background |
| `geometry.mesh` | geometria | `configs/geometry/x1.10242.yaml` | selecionado pelo experimento |
| `geometry.np` | recurso MPI ligado à execução | plataforma + override `run.tasks` | não deve permanecer como propriedade da geometria |
| nomes de namelist/streams | convenção MPAS | forecast / templates | não pertence ao experimento |
| `method.cost_type` | método de AD | `configs/assimilation/3dvar_fgat.yaml` | selecionado por `assimilation.method` |
| `method.covariance_model` | tipo de B | B matrix | selecionado por `bmatrix.name` |
| `method.covariance_date` | validade da B | B matrix / runtime | deve ser metadado validado da B |
| `method.model_name`, `model_tstep` | acoplamento MPAS-JEDI | assimilação/FGAT | configuração grossa do método |
| `method.minimizer` | minimização | assimilação | default do método, com override permitido |
| `method.ninner` | inner iterations | experimento mínimo | ajuste frequente |
| `method.gradient_norm_reduction` | convergência | assimilação | default do método; override opcional |
| `paths.data_root` | dados externos | plataforma/dataset | nunca no YAML mínimo |
| `paths.work_root`, `runtime_dir`, `rendered_dir`, `scratch_root` | diretórios | plataforma + runtime | runtime deve ser derivado do experimento/ciclo |
| `jedi.executable` | binário | plataforma | não pertence ao experimento científico |

## Classificação de `runtime.yaml`

| Grupo atual | Papel | Destino proposto | Observação |
|---|---|---|---|
| background `mpasout` e `templateFields` | insumos dependentes do tempo | background | devem ser resolvidos por template temporal |
| invariante MPAS e partição | geometria | `configs/geometry/x1.10242.yaml` | dependem da malha e do número de tarefas compatível |
| namelist/streams de outer/inner loop | perfil MPAS/JEDI | forecast e assimilação | devem ser links/renderizações definidos pelo componente |
| stream lists, `geovars`, `keptvars`, `obsop_name_map` | instalação MPAS-JEDI | plataforma / runtime-base | comuns a múltiplos experimentos |
| UFO tier-1 | dependência UFO | plataforma / observações | depende do conjunto observacional e da instalação |
| diretórios `Data/*`, `background`, `testinput` | layout runtime | template do runtime | o motor cria, não o experimento |
| arquivos de física | perfil MPAS | forecast | devem ser fornecidos pelo perfil de forecast/ambiente |
| campos exigidos no background | contrato de background | background | validação específica do tipo de background |
| `required_xtime` | consistência temporal | background / timeline | calculada por ciclo e validada |

## Demais arquivos atuais

### `variables.yaml`

Pertence ao componente de variáveis do método/experimento. Os fragmentos
existentes são reutilizáveis e devem continuar sendo resolvidos pelo loader.

Destino:

```text
configs/fragments/jedi/variables/
```

Não é necessário migrá-lo na primeira etapa.

### `observations.yaml`

Já usa uma boa separação: o experimento seleciona nomes compactos e o loader
resolve fragmentos de observadores.

Evolução proposta:

```text
configs/observations/
  sets/
    conv_basic.yaml
  instruments/
    radiosonde.yaml
    gnssro_ref_ncep.yaml
    sfc_corrected.yaml
```

O conjunto apenas define a ordem e a lista dos instrumentos. Cada instrumento
contém caminho/template, variáveis, filtros, operador, erros e parâmetros UFO.

A compatibilidade inicial pode ser mantida criando adaptadores que convertam um
`set` no formato atual de observadores resolvidos.

### `pbs.yaml`

Deve ser dividido em:

- `configs/platforms/jaci.yaml`: fila, módulos, variáveis de ambiente,
  wrappers, diretórios institucionais e defaults;
- perfil de recurso escolhido no experimento: `tasks`, walltime e, quando
  necessário, memória/nós;
- template PBS: estrutura invariável do script.

### `validation.yaml`

Permanece como contrato do baseline durante a migração. Posteriormente deverá
ser dividido entre:

- validação de compatibilidade entre componentes;
- validação de referência/regressão específica do baseline.

## Contratos que não podem ser perdidos

1. A janela FGAT de seis horas e sua relação com background e tempo de análise.
2. A disponibilidade de `templateFields` no tempo de análise, mesmo que o
   background principal esteja em outro tempo.
3. A associação entre malha, partição MPI, invariante e número de tarefas.
4. Os campos mínimos exigidos no arquivo de background.
5. A ordem dos observadores, pois ela deve permanecer determinística no YAML
   JEDI renderizado.
6. As listas de variáveis e observadores já resolvidas pelos fragmentos.
7. A idempotência da preparação de links e diretórios.
8. A ausência de submissão automática por padrão.

## Migração em duas camadas

### Camada de compatibilidade

Sem alterar o baseline existente, adicionar componentes novos e um resolvedor
que possa alimentar o renderer atual. O resultado deve ser comparável ao YAML
JEDI/PBS renderizado hoje.

### Camada de ciclo

Depois da equivalência do passo único, a timeline produzirá instâncias do
baseline para cada tempo `T`, substituindo os valores dependentes do tempo:

```text
analysis_time(T)
background_time(T)
window_begin(T)
runtime_dir(T)
background path(T)
templateFields path(T)
```

## Próxima implementação

1. Introduzir o formato de `cycle` no código sem remover o formato atual.
2. Criar um resolvedor de tempo capaz de calcular os tempos de análise,
   background e janela para 3DVar-FGAT.
3. Adicionar um comando de planejamento que apenas mostre os ciclos e suas
   dependências, sem gerar arquivos ou submeter jobs.
4. Cobrir o resolvedor com testes unitários usando o baseline `2018041500`.
