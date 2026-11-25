# Perfis computacionais independentes da máquina — contrato v1

> **Estado:** integração opt-in implementada para perfis **PBS completos**. `experiment create --machine` traduz o perfil computacional para o contrato legado de PBS, preservando os geradores científicos. **Execução local/Slurm ainda não foi implementada**; a JACI continua sendo a referência científica validada. A configuração PBS por estágio agora é obrigatória na rota `--machine`.

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
- `execution.stages`: recursos PBS explícitos por operação (`jedi`, `mpas`, `mpas_init`, `wps`, `obs2ioda`). O estágio opcional `mpas_initial` controla a primeira previsão MPAS (`science/initialization/mpas.yaml`), distinta da preparação `mpas_init_atmosphere` (`science/initialization/mpas_init.yaml`); quando ausente, a primeira previsão herda `stages.mpas`, preservando perfis existentes. Cada estágio especifica `queue`, `walltime`, `select`, `ncpus` e `mpiprocs`; os estágios MPI também precisam de `launcher`. Os valores JACI aparecem **somente no exemplo de configuração**, não são escolhidos pelo novo gerador.
- `execution.queue_limits`: mapa opcional com duração máxima permitida por fila, em **minutos**. É usado na validação da configuração de máquina antes de criar o caso.
- `execution.queue`, `walltime`: campos genéricos opcionais para schedulers; a criação científica pelo novo `--machine` exige política por estágio.
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

**Não passe `machine.yaml` em `experiment create --site`:** esse argumento continua esperando o contrato legado `site/stack/jedi/environment`.

### Criar um experimento usando o novo perfil PBS

Após preencher **todos** os caminhos de `configs/sites/jaci/machine.yaml.example` com os locais reais, copie o arquivo para um local de configuração pessoal, e teste sem interferir nos experimentos em execução:

```bash
# Os exemplos devem ser configurados antes da verificação de existência.
python -m monan_jedi_workflow.unified_cli experiment machine validate \
  /caminho/para/meu-machine.yaml --check-paths

python -m monan_jedi_workflow.unified_cli experiment create \
  /caminho/para/novo-experimento   --machine /caminho/para/meu-machine.yaml   --start 2026-01-30T00:00:00Z
```

A execução exige que o manifesto MONAN-JEDI v2 e o setup de módulos selecionado correspondam ao perfil. A seleção de diretórios `mesh_root`/`bmatrix_root` **não muda o método científico nem escolhe automaticamente uma resolução**. Em vez de modificar `site.yaml` existente, o gerador grava `machine-profile-lock.yaml` no novo caso para registrar a configuração computacional resolvida.

**Limitação:** enquanto os estágios científicos ainda gerarem PBS, o novo `--machine` aceita somente `execution.backend: pbs` com `environment.kind: modules` e os caminhos exigidos pelo runtime atual. Perfis `local` e `slurm` são válidos para inspeção, mas a tentativa de criar um caso científico com esses backends falha **antes de gerar arquivos**. Na rota `--machine`, os recursos de **JEDI, MPAS, MPAS-Init, WPS e Obs2IODA** são copiados de `execution.stages` para os blocos PBS gerados, inclusive o launcher MPI. Os parâmetros CLI legados `--pbs-queue` e `--pbs-walltime` são recusados em conjunto com `--machine`, para que não contornem a configuração validada. A rota antiga continua com os defaults conhecidos da JACI, para compatibilidade. Não confunda a externalização de recursos PBS com suporte ao backend `local`/Slurm.

## Critérios para a próxima etapa

1. **Feito no código (a validar em CI/JACI):** adaptar perfis PBS completos ao runtime legado sem alterar a ciência.
2. **Feito:** permitir `experiment create --machine`, mantendo `--site` compatível.
3. **Feito para PBS:** gerar `environment.sh`, `science/site.yaml` e `machine-profile-lock.yaml`; teste de equivalência YAML adicionado.
4. **Feito no caminho `--machine` (a validar):** recursos computacionais por estágio são obtidos do perfil, com verificação opcional dos limites de fila. **Pendente:** retirar os defaults JACI do caminho legado após migração e homologação.
5. **Pendente:** implementar e testar backend `local` real para WPS/MPAS/JEDI/Obs2IODA, sem gerar PBS.
6. **Pendente:** validar na JACI o caso completo contra o baseline, com hashes e resultados científicos; não modificar campanhas em execução.

A introdução do parser não constitui homologação da portabilidade da execução científica.
