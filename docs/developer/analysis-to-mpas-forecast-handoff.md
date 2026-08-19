# Handoff MPAS-JEDI analysis → MPAS forecast

## Decisão científica

O contrato é **B**: o forecast standalone recebe um estado MPAS completo no
horário da análise. A saída parcial do stream `analysis` não é um IC completo.

`config_do_DAcycling` não seleciona nem relaxa o stream de IC. Em
`mpas_atm_core.F`, `config_do_restart` escolhe exclusivamente `restart` ou
`input`; depois, `config_do_DAcycling` permite recalcular os campos acoplados
quando um *restart* foi alterado por DA. Com `config_do_restart=.false.`, essa
recomputação já ocorre independentemente do valor de `config_do_DAcycling`.
O flag também é encaminhado à física MYNN como `cycling`, mas não transforma
um arquivo de 13 variáveis em estado inicial completo.

Evidência local usada nesta decisão:

- `skylab-v8/mpas/src/core_atmosphere/mpas_atm_core.F:122-138`: seleção e
  leitura dos streams `input`/`restart`;
- `skylab-v8/mpas/src/core_atmosphere/mpas_atm_core.F:519-529`: recomputação
  dos diagnósticos/campos acoplados;
- `skylab-v8/mpas/src/core_atmosphere/Registry.xml:394-403`: descrição do flag;
- `skylab-v8/mpas/src/core_atmosphere/physics/mpas_atmphys_driver_pbl.F` e
  `physics_wrf/module_bl_mynn.F:536-538`: passagem à MYNN;
- o debug info do binário publicado aponta para
  `/p/projetos/monan_das/joao.gerd/work/monan-jedi-mpas/build/mpas/src/core_atmosphere`.

## Mecanismo suportado

O NCAR MPAS-Workflow não faz merge depois da variacional. Em
`bin/PrepJEDI.csh:1171-1177`, ele copia o background completo para o nome final
da análise antes de executar JEDI. MPAS-JEDI escreve o stream `analysis` nesse
arquivo. `mpas_fields_mod.F90:553-569` escolhe o stream e chama o stream
manager; `clobber_mode=overwrite` permite sobrescrever registros, enquanto
somente `truncate` trunca o arquivo (`mpas_stream_manager.F:3158-3177`). Assim,
os campos fora do stream de análise permanecem no arquivo.

Esta branch representa o mesmo mecanismo com `jedi.analysis_seed`. O preparo:

1. valida que o seed contém os campos completos declarados;
2. copia para arquivo temporário e faz `replace` atômico;
3. recusa sobrescrever um output divergente;
4. registra `.monan-jedi-workflow/analysis-seed.json`;
5. é idempotente quando o seed já está materializado.

O ciclo 2018-04-15 00Z foi reexecutado com esse contrato no job JACI
`369654.pbs-ha`. O output definitivo contém 62 variáveis: as 13 variáveis de DA
são exatamente iguais à análise parcial validada e as outras 49 são exatamente
iguais à seed. Os 62 valores armazenados também são exatamente equivalentes à
prova de conceito anterior. O workflow não introduz merge NetCDF pós-JEDI.

## Streams

- `invariant`: geometria/campos invariantes, lidos antes do IC.
- `input`: IC completo do standalone quando `config_do_restart=.false.`.
- `restart`: IC de restart somente quando `config_do_restart=.true.`.
- `background`: visão de campos necessária para leitura/escrita de estados
  background pelo MPAS-JEDI; não substitui o IC standalone.
- `analysis`: subconjunto escrito pela variacional no arquivo previamente
  semeado.
- `da_state`/`dastate`: estado de modelo publicado pelo forecast para DA. O
  caso JACI validado usa o immutable stream `da_state` com package `jedi_da`;
  o NCAR workflow também mostra uma variante configurável `dastate` com
  `stream_list.atmosphere.dastate`.

## Primeiro forecast

O template JACI fixa:

- início `2018-04-15_00:00:00` e duração `0_06:00:00`;
- `config_do_restart=.false.`;
- `config_do_DAcycling=.true.`;
- `config_IAU_option='off'`;
- `da_state output_interval='03:00:00'`;
- 128 MPI ranks e `x1.10242.graph.info.part.128`.

Produtos obrigatórios:

- `mpasout.2018-04-15_03.00.00.nc`;
- `mpasout.2018-04-15_06.00.00.nc`.

O primeiro é o background t−3 da análise 06Z; o segundo é o estado completo no
horário da análise seguinte. Nenhum deles é substituído por um restart.
