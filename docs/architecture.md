# Arquitetura do novo MONAN-JEDI Workflow

## Objetivo

Este workflow foi reiniciado para reproduzir primeiro um caso MPAS-JEDI já validado, antes de introduzir generalizações.

O primeiro caso suportado é:

- método: `3D-FGAT`;
- modelo: `MPAS`;
- covariância: `MPASstatic`;
- malha: `x1.10242`;
- ciclo: `2018041500`;
- background inicial: `2018-04-14T21:00:00Z`;
- análise: `2018-04-15T00:00:00Z`;
- janela: 6 horas;
- MPI: `np64`;
- observações: `Aircraft`, `Radiosonde`, `SfcCorrected`.

## Regra principal

O workflow não tenta ser genérico na primeira versão. Ele reproduz primeiro um caso validado. Generalizações entram depois.

## Separação conceitual

O YAML final do JEDI é gerado a partir de partes menores:

```text
experiment.yaml      informações gerais do experimento, ciclo, paths e método
runtime.yaml         arquivos necessários no diretório de execução
variables.yaml       variáveis de análise, estado e modelo
observations.yaml    observadores e arquivos IODA
pbs.yaml             recursos de fila e execução
template JEDI        estrutura final esperada pelo mpasjedi_variational.x
template PBS         script de submissão
````

## Runtime

O MPAS resolve nomes definidos dentro de `streams.atmosphere.*` relativamente ao diretório de execução. Portanto, arquivos como:

* `x1.10242.invariant.nc`;
* `templateFields.10242.nc`;
* `x1.10242.graph.info.part.64`;
* `stream_list.atmosphere.background`;
* `stream_list.atmosphere.analysis`;
* `stream_list.atmosphere.control`;
* `stream_list.atmosphere.ensemble`;

precisam existir diretamente no runtime.

## Validações obrigatórias

Antes de submeter qualquer job, o workflow deve validar:

* existência do background 21Z;
* `xtime` do background 21Z;
* existência de `templateFields.10242.nc`;
* `xtime` de `templateFields.10242.nc`;
* existência de `x1.10242.invariant.nc`;
* existência de `x1.10242.graph.info.part.64`;
* presença dos campos `ivgtyp`, `isltyp`, `landmask`, `znt`, `t2m` em `stream_list.atmosphere.background`;
* `geovars.yaml` com `air_pressure` usando `identity`;
* YAML final JEDI válido;
* PBS renderizado válido;
* `np64`.

## Fora do escopo inicial

A primeira versão não implementa:

* SABER/BUMP;
* múltiplos ciclos;
* múltiplas malhas;
* submissão automática;
* assimilação em produção;
* conversão de observações;
* geração de gráficos ou diagnósticos científicos.

