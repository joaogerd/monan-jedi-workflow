# Campanhas com ciclos nativos

A interface de campanhas representa o processo científico uma única vez e deixa as instâncias temporais para o runtime do `simpleWorkflow`.

## Separação de responsabilidades

```text
campaign.yaml  -> período e escolhas científicas
workflow.yaml  -> processo estático
state.sqlite3  -> estado de cada tarefa em cada ciclo
```

A mudança de `duration: PT72H` para `duration: PT168H` aumenta o número de ciclos executados, não o número de definições de tarefas no `workflow.yaml`.

## Inicialização

A inicialização pertence formalmente ao workflow e não é um ciclo de assimilação:

```text
condição inicial MPAS em t0-6h
        |
        v
mpas_initial_prepare
        |
mpas_initial_submit
        |
mpas_initial_wait
        |
mpas_initial_validate
        |
mpas_initial_gate
        |
initial_background
        |
background(t0)
```

O estado dessa fase é persistido pelo `simpleWorkflow`. Em um restart, tarefas de inicialização já concluídas não são executadas novamente.

O perfil da campanha declara `initial_mpas_case`. Esse case deve conter um `mpas.yaml` executável a partir de uma condição inicial válida seis horas antes da primeira análise. Para a campanha M3 iniciada em 2018-04-15 00Z, o case de inicialização começa em 2018-04-14 18Z e precisa produzir pelo menos os estados de 21Z e 00Z.

A inicialização não aceita o background 00Z já calculado como atalho. O background do primeiro ciclo é publicado a partir dos produtos do MPAS executado pela própria fase de inicialização.

## Interface única de background

Todo JEDI consome a mesma interface:

```text
work/background/<cycle_id>/trajectory.nc
work/background/<cycle_id>/state.nc
work/background/<cycle_id>/background.json
```

Para o primeiro ciclo, esses arquivos são publicados pela inicialização. Para os demais ciclos, são publicados pela integração MPAS do ciclo anterior. O JEDI não possui uma cadeia especial para o primeiro horário.

`background.json` registra a origem e checksums SHA-256. `background-check` valida a interface antes de liberar o JEDI.

## Ciclo científico

As tarefas abaixo são definidas uma única vez:

```text
background_check ----+
                     |
observations_doctor  |
        |            |
observations_prepare |
        |            |
observations_run     |
        |            |
observations_validate|
        |            |
observations_gate ---+
        |
        v
jedi_prepare
jedi_submit
jedi_wait
jedi_validate
jedi_gate
        |
        v
mpas_prepare
mpas_submit
mpas_wait
mpas_validate
mpas_gate
        |
        v
next_background   (not_last)
```

A data vem de `{cycle_time}` e demais variáveis de contexto fornecidas pelo `simpleWorkflow`; ela não faz parte do ID estrutural da tarefa.

Os ciclos são sequenciais. O ciclo seguinte só é iniciado depois que o ciclo atual conclui, e o `next_background` do ciclo atual produz a interface consumida no horário seguinte. Isso evita disparar análises independentes que apenas esperariam arquivos aparecerem.

## Observações

Obs2IODA opera no próprio `cycle_time`. Portanto, as observações utilizadas em JEDI(t) pertencem a t. O primeiro ciclo também prepara e valida suas observações dentro da campanha; elas deixam de ser um starting input especial do replay antigo.

## MPAS e previsão operacional

`mpas.lead_hours` e `mpas.forecast_contract.run_hours` representam a mesma integração e devem ser iguais. O contrato aceita horizonte maior que 6 h, desde que cubra pelo menos o próximo horário de assimilação.

Assim uma única integração de 48 h pode fornecer:

```text
analysis(t)
   |
   v
MPAS 48 h
   +-- +6 h  -> background(t+6)
   +-- +12 h -> forecast
   +-- ...
   +-- +48 h -> forecast
```

Não é criada uma segunda execução MPAS apenas para produzir o background de +6 h.

## Último ciclo

A publicação `next_background` usa `cycle_scope: not_last`, porque não existe próximo ciclo dentro da campanha.

A execução do MPAS é uma decisão diferente. Por padrão a campanha pode usar MPAS apenas onde há ciclo seguinte. Quando a ciência requer previsão a partir da última análise, declare:

```yaml
forecast:
  run_on_last_cycle: true
```

Nesse caso as tarefas MPAS usam `cycle_scope: all`, mas `next_background` continua `not_last`.

Não existe fase artificial `finalization`.

## Contagem inclusiva

`start` e `end` são inclusivos. Com `step: PT6H`:

```text
2018-04-15 00Z -> 2018-04-18 00Z = 13 ciclos
2018-04-15 00Z -> 2018-04-22 00Z = 29 ciclos
30 dias                           = 121 ciclos
365 dias                          = 1461 ciclos
```

## Restart

Use o mesmo `workflow.yaml` e o mesmo diretório `.simpleworkflow`. A identidade persistente continua sendo tarefa + ciclo; a inicialização possui namespace persistente separado. Tarefas concluídas e ainda válidas não são repetidas.

## Pré-validação na JACI

Antes de submeter uma campanha nova:

```bash
monan-jedi-workflow campaign check examples/campaigns/m3-3days-20180415.yaml
monan-jedi-workflow campaign create examples/campaigns/m3-3days-20180415.yaml
swf plan <DEST>/workflow.yaml --workdir <DEST>/.simpleworkflow
```

A execução científica de sete dias só deve ocorrer depois que a nova campanha de três dias reproduzir o processo científico do baseline validado.