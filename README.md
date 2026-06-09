# MONAN-JEDI Workflow

Workflow mínimo, controlado e Python-first para executar experimentos MPAS-JEDI no ambiente MONAN/JACI.

A primeira meta deste repositório é reproduzir um caso já validado:

- 3D-FGAT;
- MPAS-JEDI;
- malha `x1.10242`;
- ciclo `2018041500`;
- execução `np64`;
- covariância `MPASstatic`;
- observações `Radiosonde`, `GnssroRefNCEP` e `SfcCorrected`.

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
  fragments/
    jedi/
      observers/
      variables/

monan_jedi_workflow/
  Código Python do workflow.

docs/
  Documentação técnica e operacional.

tests/
  Testes unitários e testes de regressão do renderer/CLI.
```

## Instalação local

```bash
python -m pip install --upgrade pip
python -m pip install -e . pytest
```

## Testes

```bash
python -m pytest
```

O repositório possui CI com GitHub Actions. A suíte roda automaticamente em pull requests para `main` e em pushes para `main`, usando Python 3.10, 3.11 e 3.12.

## Configuração por fragmentos

O experimento baseline fica em:

```text
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/
```

As listas longas de variáveis e observadores são reutilizadas a partir de fragmentos versionados em:

```text
configs/fragments/jedi/variables/
configs/fragments/jedi/observers/
```

Assim, o experimento usa seletores compactos.

Exemplo de `variables.yaml`:

```yaml
variables:
  use: mpas_3dfgat_core
```

Exemplo de `observations.yaml`:

```yaml
observations:
  use:
    - radiosonde
    - gnssro_ref_ncep
    - sfc_corrected
```

Durante o carregamento da configuração, esses seletores são resolvidos para a estrutura expandida usada pelo validador e pelo renderer. Isso mantém o YAML final explícito, mas evita duplicação dentro dos experimentos.

## Comandos seguros

Validar a configuração do baseline:

```bash
monan-jedi-workflow validate-config configs/experiments/3dfgat_mpastatic_x1.10242_2018041500
```

Renderizar o YAML do MPAS-JEDI:

```bash
monan-jedi-workflow render-yaml configs/experiments/3dfgat_mpastatic_x1.10242_2018041500
```

Renderizar o script PBS:

```bash
monan-jedi-workflow render-pbs configs/experiments/3dfgat_mpastatic_x1.10242_2018041500
```

Esses comandos não submetem jobs. A submissão via `qsub` deve continuar sendo uma ação manual e explícita.

## Primeiro alvo operacional

O primeiro alvo é reproduzir o baseline 3DFGAT + MPASstatic que já foi validado manualmente no JACI.

Generalizações, suporte SABER/BUMP e múltiplos ciclos serão adicionados somente depois que o caso mínimo estiver versionado, validado e reproduzível.
