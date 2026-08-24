# Primeiro experimento cíclico

O primeiro experimento **nao deve comecar pelo ciclo completo**. Comece reproduzindo uma analise JEDI que ja funciona e acrescente uma parte de cada vez.

Para o caso atualmente validado em `manual-tests/baseline_bmatrix`, siga primeiro:

- [Reproduzir o baseline_bmatrix](reproduce-baseline-bmatrix.md)

Esse teste usa somente `jedi.yaml`. Nao e necessario entender nem editar `obs2ioda.yaml`, `mpas.yaml` e `workflow.yaml` antes de a analise conhecida passar pelo novo stage.

## Sequencia recomendada

```text
FASE 1  baseline JEDI conhecido
        jedi-prepare -> jedi-submit -> jedi-wait -> jedi-validate

FASE 2  observacoes
        substituir apenas Radiosonde/Sfc pelos produtos Obs2IODA

FASE 3  forecast
        analysis -> MPAS -> background da proxima analise

FASE 4  handoff
        analise 00Z -> forecast -> background 03Z -> analise 06Z

FASE 5  orquestracao
        reproduzir exatamente a mesma sequencia com simpleWorkflow
```

A matriz B ja deve existir antes do ciclo. O workflow apenas a consome.

## 1. Instale as ferramentas

```bash
cd monan-jedi-workflow
python -m pip install -e .
```

Para a **Fase 1**, apenas isto e necessario:

```bash
monan-jedi-workflow --help
```

O `simpleWorkflow` so e necessario na Fase 5.

## 2. Fase 1: reproduza o baseline atual

Nao copie os quatro YAMLs ainda. Crie um `CASE` contendo inicialmente apenas:

```text
CASE/
  jedi.yaml
  runtime-skeleton/
```

Use como fonte de verdade o caso que passa com a compilacao atual. No caso `baseline_bmatrix`, isso significa preservar inicialmente:

- `variants/3dfgat.bmatrix.yaml` sem alteracao;
- background `2018-04-14 21Z`;
- Radiosonde, GNSSRO e superficie usados no baseline;
- B SABER/BUMP (NICAS + HDIAG + VBAL);
- geometria e demais arquivos fixos do runtime;
- mesmo executavel MONAN-JEDI.

Siga o procedimento completo em [Reproduzir o baseline_bmatrix](reproduce-baseline-bmatrix.md).

O primeiro comando importante e somente:

```bash
monan-jedi-workflow jedi-prepare CASE \
  --cycle 2018-04-15T00:00:00Z
```

Ele **nao submete PBS**. Inspecione o runtime, o YAML e o PBS antes de chamar `jedi-submit`.

## 3. Fase 2: introduza Obs2IODA

Somente depois de `jedi-validate` reproduzir a analise conhecida, configure `obs2ioda.yaml`.

Nesta fase mantenha inalterados:

- B;
- background;
- geometria;
- configuracao JEDI;
- executavel.

Troque apenas as observacoes convencionais pelo output do Obs2IODA. O baseline usa tambem `GnssroRefNCEP`; GNSSRO continua sendo uma entrada separada enquanto nao houver um produtor definido no workflow.

Teste os comandos diretamente antes de qualquer DAG:

```bash
monan-jedi-workflow obs2ioda-doctor CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow obs2ioda-prepare CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow obs2ioda-run CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow obs2ioda-validate CASE --cycle 2018-04-15T00:00:00Z
```

Depois repita a analise JEDI e compare com a Fase 1.

### Baseline observacional operacional

A validacao do pipeline Obs2IODA compara, em 00Z, as observacoes comuns aos
produtos do tutorial. Isso valida a conversao, mas nao torna os arquivos GDEX
identicos ao conjunto reduzido do tutorial (974 locations de sondes, 282 de
superficie e 20 de GNSSRO).

Os produtos GDEX preservam uma colecao operacional mais completa. Para 06Z,
eles contem 2.682 locations de sondes, 154.574 de superficie e 69.198 de
GNSSRO. Esse ciclo estabelece portanto um novo baseline observacional
operacional. Comparacoes numericas da analise 06Z nao sao uma regressao contra
a analise tutorial 00Z, e os arquivos nao devem ser artificialmente reduzidos
para reproduzir as contagens do tutorial.

## 4. Fase 3: conecte o forecast MPAS

Somente depois das observacoes estarem comprovadas, configure `mpas.yaml` para iniciar a previsao a partir da analise validada.

O objetivo desta fase e responder empiricamente qual configuracao MPAS produz o estado correto de 03Z que sera usado como background da analise 06Z.

Nao assuma que `lead_hours: 3` esta cientificamente validado apenas porque aparece no exemplo. Preserve o comportamento do forecast conhecido e valide o produto.

## 5. Fase 4: prove dois ciclos manualmente

Antes do `simpleWorkflow`, prove diretamente:

```text
JEDI 2018041500
  -> MPAS iniciado pela analise 00Z
     -> background valido em 03Z
        -> JEDI 2018041506
```

O ponto critico e verificar fisicamente que o `jedi-prepare` de 06Z aponta para o produto de 03Z gerado pelo forecast de 00Z.

## 6. Fase 5: use simpleWorkflow

Somente quando a sequencia acima funcionar pelos comandos de dominio, crie/edite `workflow.yaml` e execute:

```bash
swf plan CASE/workflow.yaml

swf run CASE/workflow.yaml \
  --from 2018-04-15T00:00:00Z \
  --to   2018-04-15T06:00:00Z \
  --step PT6H
```

O `simpleWorkflow` deve apenas reproduzir a sequencia ja validada. Ele nao deve ser usado para descobrir configuracao cientifica.

## 7. Amplie a campanha

Depois do handoff 00Z -> 06Z funcionar tanto diretamente quanto pelo `simpleWorkflow`, amplie primeiro para 24 h e depois 48 h.

Nao avance para uma campanha longa antes de validar:

- analises produzidas;
- backgrounds do forecast;
- observacoes realmente usadas;
- logs JEDI/MPAS;
- horarios dos arquivos;
- restart depois de uma falha controlada.
