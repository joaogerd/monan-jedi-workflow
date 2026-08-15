# Mapeamento do baseline que passou para o template cíclico

## Fonte

A referência versionada é:

```text
configs/experiments/3dfgat_mpastatic_x1.10242_2018041500/reference/baseline_passed.yaml
```

Ela é mais importante que um tutorial histórico porque registra a configuração efetivamente usada no desenvolvimento local.

## Estratégia

A primeira versão cíclica deve alterar o mínimo possível. Parametrização temporal/path não deve ser misturada com mudança científica.

| Campo do baseline | Valor 2018041500 | Template cíclico |
|---|---|---|
| `time window.begin` | `2018-04-14T21:00:00Z` | `{window_begin_time}` |
| `time window.length` | `PT6H` | `{window_length}` |
| background filename | `...21.00.00.nc` | `{run_dir}/background/mpasout.{background_mpas_file_time}.nc` |
| background date | `21Z` | `{background_time}` |
| covariance date | `21Z` | `{background_time}` (preserva baseline) |
| geometry nml/streams | runtime fixo 2018041500 | `{run_dir}/...` |
| inner nml/streams | runtime fixo 2018041500 | `{run_dir}/...` |
| sondes input | `sondes_obs_2018041500_m.nc4` | `sondes_obs_{analysis_yyyymmddhh}_m.nc4` |
| GNSSRO input | `gnssro_obs_2018041500_s.nc4` | `gnssro_obs_{analysis_yyyymmddhh}_s.nc4` |
| superfície input | `sfc_obs_2018041500_m.nc4` | `sfc_obs_{analysis_yyyymmddhh}_m.nc4` |

## Ciência preservada

O template não altera:

- `cost type: 3D-FGAT`;
- `MPASstatic`;
- model/analysis variables;
- Radiosonde + GnssroRefNCEP + SfcCorrected;
- operadores;
- filtros;
- DRPCG;
- `ninner: 10`;
- `tstep: PT45M`.

## Observações e uma lacuna importante

O PREPBUFR convencional já trabalhado no workflow produz coleções como sondes e superfície. O observer `GnssroRefNCEP` do baseline depende de outra fonte IODA. A primeira campanha real precisa portanto garantir GNSSRO por ciclo ou, se houver decisão científica para outro conjunto observacional, criar um novo baseline validado explicitamente.

Não retire o observer silenciosamente no arquivo de orquestração.

## Runtime skeleton

O skeleton deve conter arquivos **fixos** necessários à versão atual, como namelists/streams e tabelas, mas não deve embutir arquivos que variam por ciclo e que o stage precisa linkar (background e observações). Isso evita colisões e torna a proveniência clara.
