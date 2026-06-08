# Revisão arquitetural baseada no MPAS-Workflow

Este documento resume uma revisão técnica do `monan-jedi-workflow` usando o `NCAR/MPAS-Workflow` como referência arquitetural. O objetivo não é copiar a arquitetura do MPAS-Workflow, mas extrair princípios úteis para evoluir o workflow MONAN-JEDI de forma incremental, preservando o baseline funcional.

## Escopo

O estado atual do projeto é um workflow Python-first, mínimo e controlado, focado no baseline MPAS-JEDI 3D-FGAT com covariância `MPASstatic`, malha `x1.10242`, ciclo `2018041500` e execução `np64`.

Esta revisão não executa jobs HPC, não submete PBS e não muda o comportamento operacional do baseline.

## Diagnóstico do estado atual

Pontos fortes:

- pacote Python dedicado em `monan_jedi_workflow/`;
- CLI pequena e explícita;
- comandos separados para validar, preparar runtime e renderizar artefatos;
- configuração dividida em `experiment.yaml`, `runtime.yaml`, `variables.yaml`, `observations.yaml` e `pbs.yaml`;
- preparação de runtime por links simbólicos;
- ausência de submissão automática de jobs;
- documentação indicando que a primeira meta é reproduzir um caso validado.

Pontos frágeis:

- a validação ainda está fortemente acoplada ao baseline específico;
- regras estruturais, operacionais e científicas estão misturadas em uma única função de validação;
- a configuração de PBS ainda mistura recursos de fila com detalhes de ambiente/site;
- o README menciona observações `Aircraft`, `Radiosonde` e `SfcCorrected`, enquanto o `observations.yaml` usa `Radiosonde`, `GnssroRefNCEP` e `SfcCorrected`;
- arquivos de ambiente referenciados em `pbs.yaml` precisam existir no repositório ou ser explicitamente documentados como externos.

## Lições úteis do MPAS-Workflow

O MPAS-Workflow organiza a execução em torno de cenários YAML, defaults reutilizáveis, componentes Python, templates/stubs e scripts de tarefa. Para o MONAN-JEDI, as principais lições são:

1. cenários devem controlar experimentos, sem exigir edição do núcleo Python;
2. defaults devem concentrar configurações reutilizáveis;
3. detalhes de máquina/site devem ficar separados da configuração científica;
4. a CLI deve permanecer fina, delegando lógica para módulos especializados;
5. renderização deve ser determinística e testável;
6. submissão de jobs deve permanecer explícita e nunca automática na fase inicial.

## Arquitetura alvo recomendada

```text
configs/
  experiments/
    3dfgat_mpastatic_x1.10242_2018041500/
      experiment.yaml
      runtime.yaml
      variables.yaml
      observations.yaml
      pbs.yaml
  defaults/
    methods/
    variables/
    observations/
  sites/
    jaci/
      site.yaml
      pbs.yaml
      modules.sh
      README.md
  templates/
    jedi/
    pbs/
    mpas/

monan_jedi_workflow/
  cli.py
  config.py
  yaml_utils.py
  runtime.py
  render.py
  models.py
  validators.py
  scheduler.py
  sites.py
  experiments.py
  diagnostics.py

docs/
  architecture.md
  architecture_review_mpas_workflow.md
  usage.md
  creating_experiments.md
  sites.md
  troubleshooting.md
  contributing.md

tests/
  test_yaml_utils.py
  test_config_loading.py
  test_baseline_validation.py
  test_runtime_paths.py
  test_render_yaml.py
  test_render_pbs.py
```

## Validação em camadas

A validação deve evoluir para três camadas:

```text
1. validação estrutural
   - arquivos obrigatórios
   - chaves obrigatórias
   - tipos esperados

2. validação operacional
   - paths resolvíveis
   - runtime_dir e rendered_dir coerentes
   - arquivos de runtime existentes
   - scheduler/site conhecido

3. validação científica do contrato
   - método 3D-FGAT
   - covariância MPASstatic
   - malha x1.10242
   - np64
   - variáveis esperadas
   - observadores esperados
```

O baseline atual deve continuar usando validação científica estrita. Novos experimentos devem declarar um contrato próprio, por exemplo:

```yaml
validation:
  contract: 3dfgat_mpastatic_x1.10242_v1
  strict: true
```

## Separação entre experimento e site

O experimento deve descrever ciência e layout lógico. O site deve descrever máquina, scheduler, módulos, launcher e políticas locais. A configuração JACI deve migrar gradualmente para `configs/sites/jaci/`.

Exemplo conceitual:

```yaml
# experiment.yaml
site: jaci
scheduler: pbs
```

```yaml
# configs/sites/jaci/site.yaml
site:
  id: jaci
  scheduler: pbs
  launcher: /opt/cray/pals/1.6/bin/mpiexec
  environment:
    setup_script: scripts/env/load_jaci_env.sh
    site_env: configs/sites/jaci/site.env
```

## Roadmap incremental

### Marco 0 — baseline congelado

- corrigir documentação do baseline;
- adicionar exemplos de uso dos comandos atuais;
- criar testes mínimos de carregamento, validação, runtime e renderização;
- gerar snapshots do YAML e PBS renderizados;
- marcar uma tag reprodutível.

### Marco 1 — validação modular

- criar `validators.py`;
- separar validação estrutural, operacional e científica;
- manter validador específico para o baseline atual.

### Marco 2 — suporte a sites

- criar `configs/sites/jaci/`;
- mover ambiente JACI para configuração de site;
- validar `setup_script`, `site_env` e launcher antes da renderização PBS.

### Marco 3 — múltiplos experimentos

- adicionar `list-experiments`;
- adicionar `describe-experiment`;
- permitir descoberta automática de experimentos em `configs/experiments/*`.

### Marco 4 — diagnóstico operacional

- adicionar `check-runtime`;
- validar arquivos NetCDF/HDF5 quando bibliotecas estiverem disponíveis;
- gerar relatório de diagnóstico em Markdown ou JSON.

### Marco 5 — submissão controlada

- adicionar `submit --confirm` somente após estabilização;
- registrar job id e paths de log;
- nunca submeter implicitamente.

## Estratégia Git/GitHub

Fluxo recomendado:

```text
main       branch estável
develop    integração contínua
feature/*  novas funcionalidades
fix/*      correções
docs/*     documentação
refactor/* refatorações sem mudança funcional
```

Recomendações:

- proteger `main` contra push direto;
- integrar mudanças por pull request;
- usar `develop` como branch de integração quando o projeto começar a ter múltiplas frentes;
- promover `develop` para `main` apenas após validação do baseline;
- criar tags para marcos reproduzíveis, por exemplo `v0.1.0-baseline`.

## Decisão arquitetural central

O `monan-jedi-workflow` deve ser configurável por experimento e por site, mas o núcleo Python não deve conhecer detalhes fixos de cada novo experimento.

Na prática:

- o baseline atual permanece estrito;
- novos experimentos entram por YAML;
- contratos científicos entram como validadores nomeados;
- sites entram como configuração própria;
- a CLI permanece fina;
- submissão automática continua fora do escopo até o runtime estar completamente validado.
