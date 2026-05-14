# Arquitetura do sistema

## Princípio central

A arquitetura do MONAN-JEDI-WORKFLOW foi desenhada para evitar um workflow monolítico. Cada parte tem uma responsabilidade clara:

```text
configs/      configuração científica, de site e de experimento
scripts/      comandos de preparação e execução usados pelo usuário
tools/        ferramentas Python de validação, renderização e auditoria
jobs/         templates de jobs PBS
workflow/     camada de orquestração futura, como Cylc ou ecFlow
docs/         documentação técnica histórica
docs-site/    documentação web navegável
```

## Separação de responsabilidades

| Camada | Responsabilidade |
|---|---|
| `configs/sites/` | Configuração do HPC, módulos, filas, paths e executáveis |
| `configs/experiments/` | Configuração do experimento, ciclo, dados, observers e staging |
| `configs/mpas/` | Configurações relacionadas ao MONAN/MPAS |
| `configs/jedi/` | Templates JEDI, observers e metadados |
| `scripts/setup/` | Preparação, bootstrap, checagens e staging |
| `scripts/run/` | Renderização, preparação de runtime e execução |
| `tools/` | Lógica reutilizável em Python |
| `jobs/pbs/` | Templates de submissão PBS |
| `workflow/` | Orquestração de tarefas, hoje ainda inicial |

## Separação de conceitos

O projeto separa quatro conceitos que normalmente se misturam em workflows científicos:

1. **Ciência**: variáveis, observers, covariância, janela de assimilação, background e forecast.
2. **Ambiente**: JACI, PBS, módulos, Conda, paths e executáveis.
3. **Dados**: dados externos, staging, inventário IODA e validação dos insumos.
4. **Orquestração**: como encadear tarefas em uma execução manual, PBS, Cylc ou ecFlow.

## Relação entre JEDI e MONAN/MPAS

O JEDI-MPAS executa a assimilação e produz uma análise. O MONAN/MPAS deve executar a previsão curta a partir dessa análise, gerando o background do próximo ciclo.

```text
background + observations
        ↓
   JEDI 3DVar-FGAT
        ↓
      analysis
        ↓
   MONAN/MPAS forecast
        ↓
background do próximo ciclo
```

## Sobre Cylc e ecFlow

O projeto foi inspirado no MPAS-Workflow, que usa Cylc, mas a lógica central não deve ficar presa ao Cylc. Os scripts em `scripts/setup/` e `scripts/run/` devem ser chamáveis por qualquer orquestrador.

Assim, uma futura camada `workflow/ecflow/` pode chamar os mesmos scripts que hoje seriam chamados por `workflow/cylc/`.

## Integração com scripts do grupo MONAN

Se o grupo MONAN já possui scripts próprios para rodar o modelo, eles devem ser integrados por wrappers. O workflow deve conhecer o contrato de entrada e saída, não necessariamente a implementação interna desses scripts.

Contrato esperado para forecast:

```text
entrada: análise do ciclo, arquivos estáticos, namelist, streams, ciclo
processamento: execução do script MONAN/MPAS
saída: forecast de 6 h, background do próximo ciclo, logs e status
```
