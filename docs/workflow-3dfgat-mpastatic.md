# Workflow 3D-FGAT + MPASstatic

## Objetivo

Este documento descreve o fluxo completo para reproduzir o experimento:

```
3dfgat_mpastatic_x1.10242_2018041500
```

O objetivo é reproduzir o baseline 3D-FGAT MPAS-JEDI validado no JACI utilizando:

- malha x1.10242
- 64 ranks MPI
- background centrado em 2018-04-14 21 UTC
- janela de assimilação centrada em 2018-04-15 00 UTC

---

## Ordem correta de execução

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

Esta ordem não deve ser invertida.

---

## Fase 1 — Validate Config

Responsabilidade:

- validar contrato do experimento
- verificar observadores
- verificar variáveis
- verificar diretórios necessários
- evitar criação de runtime inválido

Entrada:

```
configs/experiments/<experimento>/
```

Saída:

```
Mensagens [OK]
ou exceções
```

---

## Fase 2 — Prepare Runtime

Responsabilidade:

- criar runtime real do MPAS-JEDI
- criar links simbólicos
- montar geometria
- copiar estrutura exigida pelo MPAS

Saída:

```
build/runtime/<experimento>/<cycle>/
```

---

## Fase 3 — Render YAML

Responsabilidade:

Gerar o YAML final consumido pelo:

```
mpasjedi_variational.x
```

Saída:

```
build/rendered/<experimento>.yaml
```

---

## Fase 4 — Render PBS

Responsabilidade:

- gerar PBS
- carregar ambiente JACI
- configurar variáveis críticas
- configurar logs
- configurar MPI

Saída:

```
build/rendered/<experimento>.pbs
```

---

## Fase 5 — Execução

```bash
qsub build/rendered/3dfgat_mpastatic_x1.10242_2018041500.pbs
```

Saídas esperadas:

```
Data/states/
Data/os/
logs/
```

Sucesso esperado:

```
Run: Finishing oops::Variational with status = 0
OOPS Ending
```
