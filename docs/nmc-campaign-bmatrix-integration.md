# Campanha NMC para a matriz B

## Responsabilidade do workflow MPAS

Esta camada produz os forecasts necessários para o método NMC. Ela não executa
BFLOW, VBAL, HDIAG, NICAS, DIRAC ou SO; essas etapas pertencem ao repositório
`mpas-bmatrix-global`.

Para cada tempo válido `t`, a campanha planeja:

```text
f048: análise em t-48 h -> WPS opcional -> init MPAS -> forecast 48 h
f024: análise em t-24 h -> WPS opcional -> init MPAS -> forecast 24 h
```

Os dois forecasts precisam usar a mesma malha, partição MPI, `config_dt`,
configuração física e streams. Cada forecast precisa produzir:

```text
restart.<t>.nc
mpasout.<t>.nc
```

O restart comprova a integridade estrutural do par NMC. O `mpasout` do stream
`da_state` é o produto entregue ao BFLOW.

## Configuração

Em `workflow.yaml`, use `mode: bmatrix` e declare uma campanha:

```yaml
workflow:
  mode: bmatrix
  mesh: x1.10242
  input_source: gfs_grib2
  use_wps: auto

  bmatrix:
    campaign:
      start_valid_time: "2026-06-22T00:00:00Z"
      end_valid_time: "2026-06-22T18:00:00Z"
      valid_interval_hours: 6
      minimum_pairs: 4
      output_dir: products/nmc-campaign
      forecasts:
        f024_hours: 24
        f048_hours: 48
        products:
          restart: restart.{mpas_valid_file_time}.nc
          bflow: mpasout.{mpas_valid_file_time}.nc
```

A campanha acima cria quatro pares e oito tempos de inicialização. O primeiro
início é 48 h antes do primeiro tempo válido. Por isso, quatro pares não
correspondem simplesmente a “dois dias de dados”: a geometria temporal precisa
ser calculada a partir dos horários f024/f048.

O `mpas.run_dir` deve incluir `{lead_hours}`. Em campanhas mais longas, o mesmo
horário de inicialização pode ser usado tanto para um f024 quanto para um f048;
diretórios separados evitam colisão de `namelist`, `streams`, logs, manifestos e
produtos.

## Planejamento e execução resumível

```bash
# Não baixa, não roda WPS e não submete PBS.
monan-jedi-workflow nmc-campaign-plan experiments/bmatrix

# Comportamento dry-run: grava apenas o plano da campanha.
monan-jedi-workflow nmc-campaign-run experiments/bmatrix

# Executa somente a fronteira atual: entradas, WPS quando aplicável e preparação
# dos inits ou forecasts ainda ausentes. Não submete PBS.
monan-jedi-workflow nmc-campaign-run experiments/bmatrix --execute

# Permite submissão explícita da fronteira atual; a próxima chamada retoma após
# os produtos da camada anterior terem sido validados.
monan-jedi-workflow nmc-campaign-run experiments/bmatrix --execute --submit

# Para campanhas pequenas/smoke, aguarda e valida cada job antes de avançar.
monan-jedi-workflow nmc-campaign-run experiments/bmatrix \
  --execute --submit --wait --poll-seconds 30

# Mostra o que já existe e o que falta para cada init, restart e mpasout.
monan-jedi-workflow nmc-campaign-status experiments/bmatrix

# Só funciona quando todos os pares possuem restart e mpasout válidos.
monan-jedi-workflow nmc-campaign-export-manifest experiments/bmatrix --checksum
```

O estado é gravado em `products/nmc-campaign/nmc-campaign-execution.json`. Sem
`--wait`, a execução para após submeter todos os jobs independentes da camada
atual; isso impede forecasts de iniciarem antes de os `init.nc` correspondentes
estarem validados.

O último comando cria:

```text
products/nmc-campaign/bflow-manifest.tsv
products/nmc-campaign/bflow-manifest.json
```

O TSV é o contrato de consumo:

```tsv
valid_time	f048	f024
2026-06-22T00:00:00Z	/path/f048/mpasout.2026-06-22_00.00.00.nc	/path/f024/mpasout.2026-06-22_00.00.00.nc
```

## Consumo pelo repositório da B

```bash
mpasnmc validate-manifest --manifest products/nmc-campaign/bflow-manifest.tsv

mpasbflow all \
  --config configs/jaci-x1.10242.yaml \
  --manifest products/nmc-campaign/bflow-manifest.tsv \
  --minimum-pairs 4 \
  --clean-output
```

O consumidor valida o número mínimo de pares, cronologia, duplicidade e
existência dos arquivos antes de iniciar BFLOW. A saída do BFLOW são os
`PTB_f48mf24.nc`, que então alimentam VBAL, HDIAG e NICAS.
