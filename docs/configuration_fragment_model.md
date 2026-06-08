# Modelo de configuração por fragmentos

Este documento registra uma decisão arquitetural central para o `monan-jedi-workflow`: o usuário não deve editar manualmente um único YAML gigante do JEDI ou do MPAS. O workflow deve organizar a configuração em blocos pequenos, reutilizáveis e validados, que depois são renderizados em artefatos finais.

## Motivação

Arquivos YAML completos do JEDI podem se tornar muito grandes, especialmente quando há muitos `observers`, operadores, filtros, canais, arquivos IODA, esquemas de assimilação e opções de background error. Configurar tudo em um único arquivo é frágil, difícil de revisar e propenso a erro.

O padrão desejado é semelhante ao usado pelo `MPAS-Workflow`: manter templates e blocos menores de configuração, e renderizar o arquivo final somente no momento de preparar a execução.

## Princípio

O YAML do experimento deve declarar o que será usado. Os detalhes técnicos devem estar em fragmentos reutilizáveis.

Exemplo conceitual:

```yaml
assimilation:
  application: variational
  method: 3dfgat
  background_error: mpasstatic

observations:
  use:
    - radiosonde
    - gnssro_ref_ncep
    - sfc_corrected
```

O usuário escolhe os componentes. O workflow resolve esses nomes para arquivos de fragmentos, valida todos os blocos e monta o YAML final consumido por `mpasjedi_variational.x`.

## Estrutura sugerida

```text
configs/
  fragments/
    jedi/
      applications/
        variational_3dfgat.yaml
        variational_3dvar.yaml
        hofx.yaml

      background_error/
        mpasstatic.yaml
        saber_bump.yaml

      observers/
        radiosonde.yaml
        gnssro_ref_ncep.yaml
        sfc_corrected.yaml
        aircraft.yaml
        satwind.yaml
        amsua_n19.yaml

      obs_filters/
        preqc.yaml
        background_check.yaml
        domain_check_gnssro.yaml

    mpas/
      namelists/
        atmosphere_240km.yaml
      streams/
        atmosphere_240km.yaml
      variables/
        mpas_state_variables.yaml
        mpas_analysis_variables.yaml

  experiments/
    3dfgat_mpastatic_x1.10242_2018041500/
      experiment.yaml
      cycle.yaml
      workflow.yaml
      observations.yaml
      model.yaml
      assimilation.yaml
      runtime.yaml
      scheduler.yaml
```

## Fragmentos de observação

Cada tipo de observação deve ter seu próprio arquivo. Por exemplo:

```text
configs/fragments/jedi/observers/radiosonde.yaml
configs/fragments/jedi/observers/gnssro_ref_ncep.yaml
configs/fragments/jedi/observers/sfc_corrected.yaml
```

O experimento apenas seleciona os observadores:

```yaml
observations:
  use:
    - radiosonde
    - gnssro_ref_ncep
    - sfc_corrected
```

O renderer monta a seção final:

```yaml
cost function:
  observations:
    observers:
      - <bloco radiosonde>
      - <bloco gnssro_ref_ncep>
      - <bloco sfc_corrected>
```

## Fragmentos do método de assimilação

O método de assimilação também deve ser modular:

```text
configs/fragments/jedi/applications/variational_3dfgat.yaml
configs/fragments/jedi/background_error/mpasstatic.yaml
configs/fragments/jedi/minimizers/drpcg.yaml
```

O experimento seleciona:

```yaml
assimilation:
  application: variational
  method: 3dfgat
  background_error: mpasstatic
  minimizer: drpcg
```

## Fragmentos do MPAS

As configurações do MPAS também devem ser separadas:

```text
configs/fragments/mpas/namelists/
configs/fragments/mpas/streams/
configs/fragments/mpas/variables/
```

O experimento deve apontar para uma configuração de modelo:

```yaml
model:
  name: mpas
  mesh: x1.10242
  namelist: atmosphere_240km
  streams: atmosphere_240km
  forecast_length: PT6H
```

## Pipeline de renderização

O renderer deve seguir uma sequência determinística:

```text
1. carregar YAML do experimento
2. resolver referências para fragmentos
3. validar cada fragmento isoladamente
4. validar compatibilidade entre fragmentos
5. compor árvore YAML final em memória
6. escrever YAML final renderizado
7. validar o YAML final antes da execução
```

## Regras importantes

- fragmentos não devem conhecer o experimento;
- o experimento deve apenas selecionar e parametrizar fragmentos;
- o renderer não deve conter regra científica escondida;
- toda composição deve ser rastreável;
- o YAML final deve registrar quais fragmentos foram usados;
- o YAML final deve ser determinístico para permitir comparação via diff;
- cada fragmento deve ter testes próprios.

## Rastreabilidade

Cada arquivo renderizado deve ter um cabeçalho ou manifesto lateral indicando sua origem:

```yaml
metadata:
  generated_by: monan-jedi-workflow
  experiment_id: 3dfgat_mpastatic_x1.10242_2018041500
  cycle: 2018041500
  fragments:
    observers:
      - configs/fragments/jedi/observers/radiosonde.yaml
      - configs/fragments/jedi/observers/gnssro_ref_ncep.yaml
      - configs/fragments/jedi/observers/sfc_corrected.yaml
    background_error:
      - configs/fragments/jedi/background_error/mpasstatic.yaml
```

Quando o JEDI não aceitar uma seção `metadata`, o manifesto deve ser salvo em arquivo separado:

```text
work/<experiment_id>/rendered/<cycle>/manifest.yaml
```

## Integração com orquestradores

Esse modelo facilita integração com Cylc, ecFlow, Snakemake ou PBS puro, porque cada etapa passa a ter entradas e saídas explícitas:

```text
render_jedi_yaml
  inputs:
    - experiment YAML
    - observer fragments
    - assimilation fragments
    - model fragments
  outputs:
    - rendered JEDI YAML
    - render manifest
```

O orquestrador externo não precisa entender os detalhes do JEDI. Ele apenas executa uma etapa bem definida do workflow.

## Decisão

O `monan-jedi-workflow` deve evoluir para uma arquitetura de configuração baseada em fragmentos renderizáveis. O baseline atual pode continuar usando os YAMLs existentes, mas a próxima etapa arquitetural deve separar observadores, métodos de assimilação, background error, variáveis, namelists e streams em blocos menores, selecionados pelo YAML do experimento e renderizados pelo núcleo Python.
