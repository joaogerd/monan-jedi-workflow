# Perfis computacionais independentes da máquina — contrato v1

> **Estado:** primeira etapa da refatoração `refactor/machine-independent-site-config`. O parser, os exemplos e a validação do perfil existem; **a criação e a execução de experimentos ainda utilizam o caminho legado `site.yaml`**. Nenhuma etapa científica foi migrada. Este documento descreve o que já foi implementado e explicita o que falta.

## Objetivo

Separar **ciência** (receitas, malha selecionada, método de assimilação, conjunto de observações e calendário) de **computação** (localização das instalações e dados, sistema de submissão e ambiente de módulos). Não é responsabilidade do perfil selecionar a matriz B ou a resolução; ele informa os diretórios onde esses recursos estão disponíveis.

## Contrato v1

A nova estrutura fica em `machine.yaml`. Exemplos versionados:

- [Linux local](../../configs/sites/local/machine.yaml.example)
- [JACI](../../configs/sites/jaci/machine.yaml.example)

```yaml
schema_version: 1
machine:
  name: minha-maquina
paths:
  work_root: ${HOME}/monan-jedi
  # installation_root: /path/to/installed/runtime
  # mesh_root: /path/to/meshes
  # bmatrix_root: /path/to/matrices
execution:
  backend: local
  max_cores: 4
environment:
  kind: native
```

**Campos:**

- `machine.name`: identificador descritivo; não ativa lógica específica da JACI.
- `paths.work_root`: obrigatório e absoluto após expansão de variáveis. Os demais diretórios são opcionais no estágio inicial de validação e devem ser exigidos apenas quando a operação correspondente precisar deles.
- `paths.installation_root`, `stack_root`, `mesh_root`, `physics_root`, `bmatrix_root`, `observations_root`, `gfs_root`, `libfabric_root`, `scratch_root`: locais dos recursos computacionais/catálogos; nenhum deles seleciona um método científico.
- `execution.backend`: `local`, `pbs` ou `slurm`. **A validação desses valores não implementa, por si só, novos backends científicos.**
- `execution.queue`, `walltime`: opcionais somente para schedulers, conforme necessário.
- `execution.max_cores`: inteiro positivo; restrição computacional.
- `environment.kind`: `native` ou `modules`. Para `modules`, `environment.setup` contém o caminho do script de inicialização.

O validador **não baixa dados, não seleciona stacks, não cria diretórios e não submete jobs**. `--check-paths` exige a existência das pastas e do script de módulos declarado. A validação estrutural pode funcionar num laptop sem MPAS, JEDI, PBS, Spack ou diretórios `/p`.

## Uso disponível nesta etapa

```bash
# Em checkout da ramificação de refatoração:
experiment machine validate configs/sites/local/machine.yaml.example
experiment machine show configs/sites/local/machine.yaml.example

# Verifica existência dos diretórios definidos (configure-os primeiro):
experiment machine validate ~/.config/monan-jedi/machine.yaml --check-paths
```

Os arquivos `*.example` **não** são configurados automaticamente; é necessário criar um perfil real, com os caminhos da máquina. Para ver os argumentos:

```bash
experiment machine validate --help
```

## Compatibilidade e migração

**Não confundir `machine.yaml` v1 com `site.yaml` legado.** Ambos coexistem durante a transição:

- `configs/sites/jaci/site.yaml.example`: exemplo anterior para scripts PBS nativos e carregamento do runtime v2; não foi removido nem alterado.
- `WORKSPACE/site.yaml`: perfil persistente atualmente consumido por `experiment create`; continua sendo a fonte da execução JACI atual.
- `CASE/science/site.yaml`: configuração derivada do caso para scripts científicos e PBS.

**Não passe `machine.yaml` em `experiment create --site` neste estágio:** ele ainda espera a estrutura legada `site/stack/jedi/environment` e faria validação incompatível.

## Critérios para a próxima etapa

1. Definir o adaptador do novo perfil ao contrato de runtime, sem substituir caminhos científicos nem alterar receitas.
2. Introduzir `experiment create --machine` como seleção explícita, mantendo `--site` em compatibilidade.
3. Gerar `environment.sh` e `science/site.yaml` a partir do perfil normalizado.
4. Implementar a execução local científica apenas após separar a camada de execução PBS (hoje gerada em `experiment_start.py`).
5. Validar no laptop sem PBS/Spack e **comparar a JACI com o baseline científico existente** (scripts PBS, links e outputs), evitando mudanças durante campanhas ativas.
6. Registrar proveniência: perfil original, configuração resolvida, versão e hashes.

A introdução do parser não constitui homologação da portabilidade da execução científica.
