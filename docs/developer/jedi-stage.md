# Estágio JEDI cíclico

## Responsabilidade

`monan_jedi_workflow.jedi_stage` transforma uma configuração `jedi.yaml` e um horário de análise em um runtime executável e validável.

Ele implementa quatro operações públicas:

```text
prepare_jedi
submit_jedi
wait_jedi
validate_jedi
```

A CLI expõe as mesmas operações como `jedi-prepare`, `jedi-submit`, `jedi-wait` e `jedi-validate`.

## Não responsabilidade

O módulo não:

- escolhe o próximo ciclo;
- executa Obs2IODA;
- executa a previsão MPAS;
- implementa retry global;
- conhece simpleWorkflow/ecFlow/Cylc;
- constrói a matriz B.

## Background inicial e subsequente

`jedi.cycle.first_cycle` identifica o ciclo que usa `background.initial_source`. Os demais usam `background.source`, normalmente apontando para o forecast do ciclo anterior.

Isso codifica a única bifurcação estrutural necessária sem colocar lógica de orquestração no módulo.

## Runtime skeleton

`jedi.runtime.skeleton` é opcional. Quando configurado, representa uma fotografia de runtime **compatível com o executável atual**. O conteúdo é copiado uma única vez para o diretório do ciclo.

Um manifesto registra a origem do skeleton. Se uma execução posterior tentar usar outro skeleton no mesmo `run_dir`, o workflow falha em vez de misturar silenciosamente dois baselines.

Essa proteção existe porque arquivos relativos do MPAS/JEDI (streams, tabelas, listas e static assets) podem mudar entre versões mesmo quando o YAML parece semelhante.

## Links e templates

`links` materializa entradas grandes por link simbólico. O código nunca sobrescreve um arquivo real já existente no destino.

`templates` usa somente `str.format` com o contexto declarado. Não há `eval`, expansão shell ou execução de comandos durante renderização.

## Estados auxiliares dependentes do ciclo

Quando o MPAS-JEDI usa `templateFields.*.nc`, configure
`jedi.analysis_base_state.template_fields_target`. O stage valida que o estado
MPAS completo contém o `xtime` do `analysis_time` e materializa o target como
link para esse estado. Isso substitui de forma atômica um `templateFields` obsoleto que
tenha vindo do skeleton e torna uma segunda preparação idempotente.

Os arquivos científicos da B continuam externos e estáticos. O horário lógico
de um State que lê HDIAG é outra coisa: o campo `date` do YAML deve usar
`{analysis_time}` para que o `validTime` do FieldSet coincida com o incremento
do ciclo. Não copie, renomeie nem regenere `mpas.stddev.nc` por causa desse
metadado lógico.

## PBS

`prepare` apenas escreve o PBS. `submit` é a primeira operação com efeito no scheduler.

O job PBS muda para o `run_dir`, exporta somente o ambiente declarado e executa:

```text
launcher -n mpiprocs command...
```

## Manifests

Arquivos internos ficam em:

```text
RUN/.monan-jedi-workflow/
  analysis-output-initialization.json
  jedi-submission.json
  jedi-validation.json
  jedi-artifacts.json
  skeleton.json            # quando aplicável
```

`jedi-artifacts.json` é a interface simples de publicação dos produtos validados. Ele não contém conhecimento do orquestrador.

## Idempotência

- links iguais são reutilizados;
- um PBS já submetido é reutilizado por padrão;
- `--resubmit` permite nova submissão explícita;
- skeleton já copiado não é recopiado;
- validação pode ser repetida sem alterar os produtos científicos.

## Falhas deliberadas

O estágio falha cedo quando:

- uma entrada não existe;
- um target real seria sobrescrito;
- um placeholder é desconhecido;
- `model.tstep` lógico difere do `config_dt` físico do outer MPAS;
- o skeleton mudou para um runtime já preparado;
- `qsub` não retorna Job ID;
- o log não possui os marcadores requeridos;
- um output obrigatório não existe ou está vazio.
