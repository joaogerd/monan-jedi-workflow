# Plano de validação do Cycling DA no JACI

Este documento separa claramente **software implementado/testado** de **comportamento científico/HPC ainda não comprovado**.

## Objetivo

Validar incrementalmente o primeiro ciclo 3D-FGAT e o handoff para o segundo ciclo sem misturar, na mesma investigação, mudanças de B, conjunto observacional, resolução ou método de assimilação.

## Princípio

Comece do caso que já passou e altere somente o que é necessário para introduzir dependência temporal entre ciclos.

Não comece por uma campanha longa.

## Fase 0 — congelar a referência

Registrar antes de qualquer execução:

- commit/build atual do MONAN-JEDI;
- executável JEDI;
- executável MPAS;
- `baseline_passed.yaml` efetivamente compatível;
- runtime fixo exigido pela versão;
- malha/invariant/static;
- `graph.info.part.64` (ou ranks efetivamente escolhidos);
- B MPASstatic validada;
- fontes de observação disponíveis.

Se o `baseline_passed.yaml` do repositório não representar mais a build atual, atualize primeiro a referência e documente a diferença.

## Fase 1 — preparar o skeleton JEDI

Criar um skeleton a partir do runtime que passa.

O skeleton deve conter arquivos fixos da versão atual, mas não deve embutir produtos dependentes do ciclo que serão montados pelo stage:

- background;
- observações daquele horário;
- outputs anteriores;
- análise de outro ciclo.

Rodar:

```bash
monan-jedi-workflow cycle-doctor CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow jedi-prepare CASE --cycle 2018-04-15T00:00:00Z
```

Antes de submeter, inspecionar manualmente:

```text
work/jedi/20180415T000000Z/
```

Confirmar:

- background link aponta para 2018-04-14 21Z;
- observações apontam para 2018041500;
- B é a desejada;
- `variational.yaml` preserva o baseline;
- namelist/streams são os corretos;
- PBS possui ranks/fila/ambiente esperados.

## Fase 2 — reproduzir somente a análise 2018041500

Executar manualmente pelos stages para isolar erros:

```bash
monan-jedi-workflow jedi-submit CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow jedi-wait CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow jedi-validate CASE --cycle 2018-04-15T00:00:00Z
```

Critérios:

- PBS completa;
- marcador de sucesso atual é confirmado;
- analysis declarado existe e é não vazio;
- `jedi-artifacts.json` aponta para o arquivo correto;
- outputs observacionais necessários para diagnóstico existem, quando habilitados;
- resultado é compatível com a rodada manual/baseline dentro da expectativa científica.

Se o nome real do output ou marcador mudou, atualize o contrato do caso; não adicione heurísticas genéricas ao código só para acomodar uma versão.

## Fase 3 — forecast a partir da análise 00Z

Preparar o MPAS usando exatamente a análise validada.

```bash
monan-jedi-workflow mpas-prepare CASE --cycle 2018-04-15T00:00:00Z
```

Antes de submeter, confirme qual integração é necessária para produzir o estado válido em 03Z usado como background da análise 06Z.

O template de referência usa `lead_hours: 3` por simplicidade, mas isso **não é ainda uma conclusão científica/operacional**. O runtime atual pode exigir uma integração maior com saída intermediária.

Depois:

```bash
monan-jedi-workflow mpas-submit CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow mpas-wait CASE --cycle 2018-04-15T00:00:00Z
monan-jedi-workflow mpas-validate CASE --cycle 2018-04-15T00:00:00Z
```

Critério principal: o arquivo que será usado como background da análise 06Z existe, é compatível e possui valid time 03Z.

## Fase 4 — segundo ciclo 2018041506

Rodar primeiro:

```bash
monan-jedi-workflow jedi-prepare CASE --cycle 2018-04-15T06:00:00Z
```

Esse é o teste mais importante do handoff.

Confirmar que o background link do ciclo 06Z aponta para o produto 03Z da previsão inicializada pela análise 00Z, e não para um arquivo externo ou background antigo.

O runtime MPAS também possui dois contratos temporais que precisam acompanhar
o novo ciclo:

- `templateFields.*.nc` deve resolver para um estado MPAS cujo `xtime` seja o
  horário inicial da geometria. Ele não é um arquivo estático reutilizável de
  outro ciclo;
- a data declarada para o arquivo HDIAG no YAML deve ser o horário da análise,
  embora o conteúdo da B continue estático e não seja regenerado. Uma data
  lógica antiga produz incompatibilidade entre os `validTime` dos FieldSets.

Depois executar/validar JEDI e forecast do ciclo 06Z.

### Evidência da campanha 2018041506

Em 2026-08-24, a sequência validada chegou a:

```text
JEDI 00Z -> análise completa 00Z -> MPAS 00Z-06Z
         -> Obs2IODA operacional 06Z -> JEDI 06Z
```

O JEDI 06Z terminou com status OOPS zero usando 128 ranks e preservou
exatamente as 50 variáveis fora do stream `analysis`. O conjunto operacional
processado foi maior que o tutorial: os ObsSpaces carregaram 2.682 locations
de Radiosonde, 68.951 de GnssroRefNCEP e 138.449 de SfcCorrected. O forecast
seguinte, 06Z-12Z, ainda não faz parte desta evidência;
portanto a ciclagem multi-ciclo completa continua pendente.

## Fase 5 — reproduzir os dois ciclos com simpleWorkflow

Somente depois das chamadas manuais funcionarem:

```bash
swf plan CASE/workflow.yaml
swf run CASE/workflow.yaml \
  --from 2018-04-15T00:00:00Z \
  --to   2018-04-15T06:00:00Z \
  --step PT6H
```

O resultado científico deve ser o mesmo das execuções diretas. O orquestrador não pode alterar runtimes ou horários.

## Fase 6 — teste de restart

Introduzir uma falha controlada, por exemplo configurando temporariamente um input inexistente para uma etapa posterior.

Após corrigir:

- tarefas anteriores válidas devem ser reutilizadas;
- a etapa falha deve ser reexecutada;
- nenhuma análise já submetida deve ser duplicada sem ação explícita;
- nenhum `validate` pode ser pulado porque o PBS terminou.

## Fase 7 — campanha curta

Expandir para 24–48 h antes de uma campanha científica longa. Avaliar:

- consistência temporal;
- estabilidade do modelo após análise;
- OmB/OmA;
- incrementos;
- conservação/ruído relevante;
- crescimento de espaço em disco;
- comportamento de filas/restart.

## Observações ainda abertas

### GNSSRO

O baseline versionado usa `GnssroRefNCEP`. O PREPBUFR convencional não supre essa coleção. É necessário:

- fornecer o IODA GNSSRO por ciclo; ou
- criar e validar explicitamente um novo baseline com outro conjunto de observações.

Não retire o observer apenas na DAG.

### Matriz B

Para provar a ciclagem, prefira inicialmente a mesma `MPASstatic` do baseline que passou. A nova B desenvolvida no projeto deve entrar depois que o ciclo estiver provado, para não investigar duas mudanças científicas ao mesmo tempo.

### Diagnósticos

Depois que os primeiros ciclos passarem, integrar a saída com `monan-jedi-diagnostics` é um próximo passo natural, mas não é requisito para provar a mecânica do ciclo.
