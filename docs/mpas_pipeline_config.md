# Configuração de alto nível do pipeline MPAS

`pipeline.yaml` contém as decisões do experimento. Ele não substitui os arquivos de adaptador `wps.yaml`, `mpas_init.yaml`, `mpas.yaml` e `obs2ioda.yaml`; eles descrevem apenas como cada binário externo é chamado.

## Exemplo com entrada local já preparada

```yaml
pipeline:
  work_root: ./work/{cycle_yyyymmddhh}
  forecast_hours: 6

  inputs:
    assets:
      - name: initial_input
        provider: local
        format: mpas_init
        path: /dados/mpas/init.{cycle_yyyymmddhh}.nc

  static:
    assets:
      mesh: /dados/mpas/x1.10242.grid.nc
      partition: /dados/mpas/x1.10242.graph.info.part.128
      invariant: /dados/mpas/x1.10242.invariant.nc

  stages:
    mode: forecast
    wps: false

  mpas:
    mesh: x1.10242
    nproc: 128
    dt_seconds: 60

  adapters:
    stage_config_dir: .
```

## Exemplo GFS explícito

```yaml
pipeline:
  work_root: ./work/{cycle_yyyymmddhh}
  forecast_hours: 6

  inputs:
    assets:
      - name: gfs_grib2
        provider: gfs_http
        format: grib2
        path: ./cache/gfs.{cycle_yyyymmddhh}.f000.grib2
        url_template: https://provedor.example/gfs/{cycle_yyyymmddhh}/f000.grib2
        sha256: <opcional-64-hex>

  static:
    assets:
      mesh: /dados/mpas/x1.10242.grid.nc
      partition: /dados/mpas/x1.10242.graph.info.part.128
      invariant: /dados/mpas/x1.10242.invariant.nc

  stages:
    mode: forecast
    wps: auto
```

Com `wps: auto`, apenas entradas declaradas como `format: grib2` ativam WPS/UNGRIB. A URL é declarada pelo experimento para evitar acoplamento a uma infraestrutura externa específica.

## Comandos

```bash
monan-jedi-mpas validate pipeline.yaml --cycle 2026-06-26T00:00:00Z
monan-jedi-mpas plan pipeline.yaml --cycle 2026-06-26T00:00:00Z
monan-jedi-mpas prepare pipeline.yaml --cycle 2026-06-26T00:00:00Z --dry-run
monan-jedi-mpas status pipeline.yaml --cycle 2026-06-26T00:00:00Z
```

`prepare --fetch` é a única operação que pode baixar uma entrada remota declarada. Sem `--fetch`, `validate` e `plan` não fazem rede nem alteram arquivos.

## Reuso seguro

O estado do ciclo é salvo em `work_root/.monan-jedi-mpas/state/<cycle_id>`. Uma etapa pode ser reutilizada somente quando sua configuração e seus produtos declarados permanecem válidos. Use `--force` apenas para reconstrução deliberada.
