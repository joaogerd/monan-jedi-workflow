# MONAN-JEDI Workflow

Interface para configurar e executar experimentos cíclicos MONAN + JEDI usando
simpleWorkflow.

## Por onde começar

Se você quer **rodar um experimento**, não navegue pelos diretórios procurando
YAMLs. Siga apenas esta sequência:

1. [Tutorial: criar e rodar um caso](docs/tutorial.md)
2. [Configuração da campanha](docs/configuration/campaign.md)
3. [Configuração MONAN/MPAS](docs/configuration/mpas.md)
4. [Configuração das observações](docs/configuration/observations.md)
5. [Configuração JEDI](docs/configuration/jedi.md)
6. [Diagnóstico, status e restart](docs/troubleshooting.md)

O tutorial parte de um template único e mostra **qual arquivo copiar, o que
editar, como validar e como executar**.

## Modelo mental

O usuário configura a ciência; o workflow automatiza a mecânica:

```text
campaign.yaml
     |
     +-- período e cadência
     +-- profile científico
              |
              +-- JEDI
              +-- observações
              +-- MONAN/MPAS
              +-- inicialização
     |
     v
monan-jedi-workflow
     |
     v
simpleWorkflow
     |
     +-- Obs2IODA
     +-- JEDI
     +-- MONAN/MPAS
     +-- próximo ciclo
```

Nenhuma escolha científica deve estar escondida no código. Data, malha,
níveis, timestep, observações, B, recursos MPI/PBS e caminhos pertencem à
configuração do experimento ou ao contrato instalado do MONAN-JEDI.

## Instalação

A campanha usa três componentes, com responsabilidades diferentes:

1. **MONAN-JEDI** fornece o runtime científico instalado: MONAN/MPAS,
   MPAS-JEDI e Obs2IODA.
2. **simpleWorkflow** executa o grafo de tarefas e mantém estado/restart.
3. **monan-jedi-workflow** traduz o caso científico para esse grafo.

Instale o orquestrador:

```bash
pip install simpleworkflow
swf --help
```

Instale esta interface:

```bash
git clone https://github.com/joaogerd/monan-jedi-workflow.git
cd monan-jedi-workflow
python -m pip install -e .
monan-jedi-workflow --help
```

O MONAN-JEDI deve estar previamente instalado e validado no site. No JACI, o
usuário seleciona explicitamente:

```bash
export MONAN_JEDI_INSTALL_ROOT=/caminho/para/monan-jedi-instalado
export STACK_ROOT=/caminho/para/spack-stack
```

O workflow lê
`${MONAN_JEDI_INSTALL_ROOT}/share/monan-jedi/install-manifest.json`; não
repete internamente a identidade do stack.

## Interface normal

Depois de configurar o experimento:

```bash
monan-jedi-workflow campaign check campaign.yaml
monan-jedi-workflow campaign create campaign.yaml
monan-jedi-workflow campaign run campaign.yaml
monan-jedi-workflow campaign status campaign.yaml
```

Comece com `P3D`. Depois de validar cientificamente os três dias, mantenha a
mesma configuração científica e altere somente o período para `P7D`,
`P30D` ou `P365D`.

## Desenvolvimento

Detalhes internos do motor não fazem parte do caminho normal do usuário. O
código e os testes preservam os contratos dos stages e da integração com
simpleWorkflow. O estado anterior à simplificação foi preservado na branch
`archive/pre-cleanup-2026-10-01`.
