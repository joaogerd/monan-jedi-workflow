# Primeiro experimento cíclico

Este é o caminho curto para executar uma campanha de assimilação usando os stages do `monan-jedi-workflow` e o `simpleWorkflow` como orquestrador de pesquisa.

## 1. Instale as ferramentas

```bash
cd monan-jedi-workflow
python -m pip install -e .
```

Instale o `simpleWorkflow` no mesmo ambiente Python ou em um ambiente onde `swf` e `monan-jedi-workflow` estejam no `PATH`.

Confirme:

```bash
monan-jedi-workflow --help
swf --help
```

## 2. Crie o caso

Use como ponto de partida:

```text
examples/simpleworkflow/cycled_da/
```

Um caso completo contém:

```text
CASE/
  jedi.yaml
  mpas.yaml
  obs2ioda.yaml
  workflow.yaml
```

Copie os templates e edite os caminhos marcados. Para Obs2IODA, reutilize um perfil já testado em `examples/obs2ioda/` quando ele corresponder ao conjunto de dados desejado.

## 3. Use somente assets da versão atual

Antes da primeira rodada, identifique o baseline que funciona com a compilação atual do MONAN-JEDI e use dele:

- executáveis;
- YAML variacional;
- namelists/streams;
- runtime skeleton;
- mesh/static/invariant;
- graph partition;
- observações compatíveis;
- matriz B validada.

O tutorial histórico de Cycling DA é referência conceitual. Não copie seus arquivos científicos literalmente para uma versão diferente do MPAS-JEDI.

## 4. Faça o preflight

```bash
monan-jedi-workflow cycle-doctor CASE \
  --cycle 2018-04-15T00:00:00Z
```

O doctor é read-only. Ele não cria runtime e não submete PBS.

## 5. Confira a DAG

```bash
swf plan CASE/workflow.yaml
```

Para o ciclo de referência, a ordem é:

```text
Obs2IODA
   -> JEDI analysis
      -> MPAS forecast
         -> próximo ciclo
```

A matriz B já deve existir antes do ciclo.

## 6. Rode somente um ciclo primeiro

```bash
swf run CASE/workflow.yaml \
  --cycle-time 2018-04-15T00:00:00Z
```

Depois confira:

```bash
swf status CASE/workflow.yaml
```

Não avance para uma campanha longa antes de validar:

- análise produzida;
- background do forecast;
- observações usadas;
- logs JEDI/MPAS;
- horários dos arquivos.

## 7. Teste o handoff para o segundo ciclo

Quando o primeiro ciclo estiver correto:

```bash
swf run CASE/workflow.yaml \
  --from 2018-04-15T00:00:00Z \
  --to   2018-04-15T06:00:00Z \
  --step PT6H
```

O ponto crítico é comprovar que a análise `00Z` inicializa a previsão e que o produto correto dessa previsão é usado como background da análise `06Z`.

## 8. Amplie a campanha

Só depois do handoff de dois ciclos:

```bash
swf run CASE/workflow.yaml
```

O período padrão vem do bloco `cycle:` em `workflow.yaml`.
