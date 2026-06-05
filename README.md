# MONAN-JEDI Workflow

Workflow mínimo, controlado e Python-first para executar experimentos MPAS-JEDI no ambiente MONAN/JACI.

A primeira meta deste repositório é reproduzir um caso já validado:

- 3D-FGAT;
- MPAS-JEDI;
- malha `x1.10242`;
- ciclo `2018041500`;
- execução `np64`;
- covariância `MPASstatic`;
- observações `Aircraft`, `Radiosonde` e `SfcCorrected`.

Este repositório não é uma continuação direta do workflow anterior. Ele foi reiniciado para evitar mistura entre engenharia reversa, testes temporários e configuração operacional.

## Princípios

1. Começar por um caso validado.
2. Manter o workflow pequeno e explícito.
3. Usar Python para renderização e validação.
4. Evitar shell complexo.
5. Não submeter jobs automaticamente.
6. Validar runtime, YAML e PBS antes de qualquer execução.
7. Não versionar dados grandes, saídas, logs ou diretórios `build/`.

## Estrutura

```text
configs/
  experiments/
    3dfgat_mpastatic_x1.10242_2018041500/
  templates/
    jedi/
    pbs/

monan_jedi_workflow/
  Código Python do workflow.

docs/
  Documentação técnica e operacional.

tests/
  Testes unitários.
````

## Primeiro alvo operacional

O primeiro alvo é reproduzir o baseline 3DFGAT + MPASstatic que já foi validado manualmente no JACI.

Generalizações, suporte SABER/BUMP e múltiplos ciclos serão adicionados somente depois que o caso mínimo estiver versionado, validado e reproduzível.
