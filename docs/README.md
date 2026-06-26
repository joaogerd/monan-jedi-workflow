# Documentação do MONAN-JEDI Workflow

Esta documentação descreve o fluxo operacional do workflow MONAN-JEDI para o experimento `3dfgat_mpastatic_x1.10242_2018041500` e seus componentes reutilizáveis.

O objetivo é registrar, de forma clara e reproduzível, o que entra no processo, o que sai, qual a ordem correta de execução e por que cada etapa é necessária.

## Documentos disponíveis

1. [Workflow 3D-FGAT + MPASstatic](workflow-3dfgat-mpastatic.md)
2. [Configuração do experimento](configuracao-experimento.md)
3. [Preparação do runtime](preparacao-runtime.md)
4. [Renderização do YAML e do PBS](renderizacao-yaml-pbs.md)
5. [Execução PBS no JACI](execucao-pbs-jaci.md)
6. [Entradas e saídas](entradas-e-saidas.md)
7. [Diagnóstico e logs](diagnostico-e-logs.md)
8. [Pipeline operacional Obs2IODA](obs2ioda-pipeline.md)
9. [Obs2IODA com PREPBUFR no JACI](obs2ioda-prepbufr.md)

## Fluxo resumido

A ordem correta para o baseline de assimilação é:

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

python3 -m monan_jedi_workflow.cli submit --wait \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500

python3 -m monan_jedi_workflow.cli validate-run \
  configs/experiments/3dfgat_mpastatic_x1.10242_2018041500
```

O Obs2IODA pode ser preparado e validado independentemente por ciclo antes de integrá-lo a esse caso. Consulte os documentos específicos para o contrato de conversão e para o comportamento testado com PREPBUFR no JACI.

## Conceito central

O YAML do JEDI não é suficiente para executar o MPAS-JEDI. A aplicação também depende do diretório de execução, pois o MPAS resolve vários arquivos de forma relativa, incluindo arquivos de stream, tabelas físicas, arquivos estáticos, decomposição de malha, `templateFields` e listas de streams.

Por isso, este workflow separa o processo em três responsabilidades principais:

- os arquivos YAML em `configs/` descrevem o experimento;
- o comando `prepare-runtime` monta o diretório real de execução;
- os comandos `render-yaml`, `render-pbs`, `submit --wait` e `validate-run` produzem, executam e validam o caso.
