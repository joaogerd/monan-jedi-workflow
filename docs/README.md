# Documentação do MONAN-JEDI Workflow

Esta documentação descreve o fluxo operacional do workflow MONAN-JEDI para o experimento `3dfgat_mpastatic_x1.10242_2018041500`.

O objetivo é registrar, de forma clara e reproduzível, o que entra no processo, o que sai, qual a ordem correta de execução e por que cada etapa é necessária.

## Documentos disponíveis

1. [Workflow 3D-FGAT + MPASstatic](workflow-3dfgat-mpastatic.md)
2. [Configuração do experimento](configuracao-experimento.md)
3. [Preparação do runtime](preparacao-runtime.md)
4. [Renderização do YAML e do PBS](renderizacao-yaml-pbs.md)
5. [Execução PBS no JACI](execucao-pbs-jaci.md)
6. [Entradas e saídas](entradas-e-saidas.md)
7. [Diagnóstico e logs](diagnostico-e-logs.md)

## Fluxo resumido

A ordem correta do processo é:

```bash
python3 -m py_compile monan_jedi_workflow/*.py

python3 -m monan_jedi_workflow.cli validate-config \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

python3 -m monan_jedi_workflow.cli prepare-runtime \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

python3 -m monan_jedi_workflow.cli render-yaml \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

python3 -m monan_jedi_workflow.cli render-pbs \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

qsub build/rendered/3dfgat_mpastatic_x1.10242_2018041500.pbs
```

O `prepare-runtime` deve ser executado antes da renderização final e antes do `qsub`, porque o MPAS-JEDI depende de arquivos resolvidos relativamente ao diretório de execução.

## Conceito central

O YAML do JEDI não é suficiente para executar o MPAS-JEDI. A aplicação também depende do diretório de execução, pois o MPAS resolve vários arquivos de forma relativa, incluindo arquivos de stream, tabelas físicas, arquivos estáticos, decomposição de malha, `templateFields` e listas de streams.

Por isso, este workflow separa o processo em três responsabilidades principais:

- os arquivos YAML em `configs/` descrevem o experimento;
- o comando `prepare-runtime` monta o diretório real de execução;
- os comandos `render-yaml` e `render-pbs` geram os arquivos finais consumidos pelo JEDI e pelo PBS.
