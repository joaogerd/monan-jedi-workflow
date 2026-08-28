# Portabilidade entre orquestradores

## Objetivo

O workflow executado com `simpleWorkflow` durante a pesquisa deve poder ser reproduzido no ecFlow usado pela operação do INPE ou em Cylc sem portar a lógica científica dos stages.

O que é transferido é a **dependência entre tarefas**, não a implementação de cada tarefa.

## Workflow de referência

```text
obs_doctor
  -> obs_prepare
  -> obs_run
  -> obs_validate
  -> jedi_prepare
  -> jedi_submit
  -> jedi_wait
  -> jedi_validate
  -> mpas_prepare
  -> mpas_submit
  -> mpas_wait
  -> mpas_validate
```

Depois de `mpas_validate`, o orquestrador avança para o próximo analysis time.

## simpleWorkflow

A pesquisa usa um YAML explícito:

```yaml
- name: jedi_prepare
  depends_on: [obs_validate]
  argv:
    - monan-jedi-workflow
    - jedi-prepare
    - "{experiment_dir}"
    - --cycle
    - "{cycle_time}"
```

O arquivo completo em `examples/simpleworkflow/cycled_da/` é a implementação executável de referência do workflow.

## ecFlow

Uma eventual suite ecFlow precisa reproduzir a mesma relação, conceitualmente:

```text
suite monan_jedi_da
  family cycle
    task obs_prepare
    task obs_run          trigger obs_prepare == complete
    task obs_validate     trigger obs_run == complete
    task jedi_prepare     trigger obs_validate == complete
    task jedi_submit      trigger jedi_prepare == complete
    task jedi_wait        trigger jedi_submit == complete
    task jedi_validate    trigger jedi_wait == complete
    task mpas_prepare     trigger jedi_validate == complete
    task mpas_submit      trigger mpas_prepare == complete
    task mpas_wait        trigger mpas_submit == complete
    task mpas_validate    trigger mpas_wait == complete
```

Cada script ecFlow deve ser fino. Por exemplo, `jedi_prepare.ecf` deve essencialmente carregar o ambiente operacional e executar:

```bash
monan-jedi-workflow jedi-prepare "$CASE_DIR" --cycle "$CYCLE_ISO"
```

Não copie para o `.ecf`:

- cálculo do horário do background;
- renderização do YAML JEDI;
- criação dos links da B/observações;
- validação dos outputs;
- regras de malha;
- parsing específico de logs JEDI.

Essas regras pertencem ao domínio e já são testadas no pacote.

## Cylc

O mesmo princípio se aplica a uma configuração Cylc. Ela deve expressar dependências e calendário; os scripts continuam chamando os mesmos comandos públicos.

## O que pode mudar entre orquestradores

É aceitável que cada ambiente implemente de forma própria:

- calendário/repeat;
- retries de infraestrutura;
- limites operacionais;
- eventos/notificações;
- visualização;
- retenção de logs do orquestrador;
- política de recursos e filas quando a operação central decidir gerenciá-los externamente.

## O que não pode mudar silenciosamente

Uma tradução não deve mudar:

- ordem científica das etapas;
- significado de `cycle_time`;
- inputs/outputs de cada stage;
- contrato de validação;
- versão dos artefatos científicos;
- conjunto observacional;
- B utilizada;
- runtime/model configuration.

Se uma dessas mudanças for necessária na operação, ela é mudança de **caso científico/domínio**, não simples tradução de orquestrador.

## Estratégia de aceitação da futura tradução ecFlow

Antes de considerar a suite operacional equivalente:

1. escolha uma campanha curta já validada com simpleWorkflow;
2. execute a mesma janela temporal via ecFlow;
3. compare os manifests de domínio ciclo a ciclo;
4. compare checksums/metadata dos produtos científicos relevantes;
5. confirme que falhas/restart não pulam `validate`;
6. documente diferenças deliberadas de infraestrutura.

O objetivo é que simpleWorkflow e ecFlow sejam duas formas de dirigir o mesmo sistema, e não duas implementações diferentes do MONAN-JEDI.
