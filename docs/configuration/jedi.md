# Configuração JEDI

O `jedi.yaml` descreve uma análise MPAS-JEDI. Comece por
`examples/case/jedi.yaml`.

## Estrutura

```yaml
jedi:
  cycle: ...
  variables: ...
  run_dir: ...
  runtime: ...
  background: ...
  analysis_base_state: ...
  links: ...
  templates: ...
  nonlinear_trajectory: ...
  pbs: ...
  validation: ...
```

## Chaves principais

**cycle.step_hours** define o intervalo entre análises.

**cycle.background_offset_hours** define o deslocamento do estado usado para
iniciar a trajetória/background em relação ao horário da análise.

**cycle.window_hours** define a largura da janela de assimilação.

**variables** reúne caminhos e valores científicos reutilizados, incluindo B,
observações e runtime.

**runtime.skeleton** contém somente assets fixos. Não deve conter backgrounds,
observações ou outputs dependentes do ciclo.

**background** define a origem do primeiro background e dos backgrounds
produzidos pelos forecasts anteriores.

**analysis_base_state** define o estado MPAS completo usado como base da análise
e o nome do produto. A chave `target` é a fonte de verdade desse nome; o motor
não escolhe um nome de método automaticamente.

**links** declara B, observações e outros arquivos necessários no runtime.

**templates** declara o YAML variacional e os namelists MPAS-JEDI.

**nonlinear_trajectory** liga o YAML variacional à trajetória não linear FGAT,
quando aplicável.

**pbs** define recursos e comando do MPAS-JEDI.

**validation** define log, marcadores de término e produto científico esperado.

O YAML variacional referenciado em `templates` contém as escolhas detalhadas
de DA: geometry, variáveis de estado/controle, B, observers, operadores, QC,
erros de observação e minimização. O baseline 2025 será a referência concreta
dessas escolhas; o workflow não inventará defaults científicos.
