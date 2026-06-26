# Obs2IODA com PREPBUFR no JACI

Este documento registra o contrato efetivamente testado para converter PREPBUFR com o binário `obs2ioda_v3` compilado no bundle MONAN-JEDI.

## Ambiente

O executável depende do ambiente JACI carregado pelo workflow. Antes de testar manualmente ou executar um caso que use o binário, carregue:

```bash
source scripts/load_jaci_env.sh
```

Sem esse ambiente, o carregador dinâmico pode não localizar bibliotecas como `libfabric.so.1`.

## Contrato do executável testado

O binário publicado em `builds/monan-jedi-mpas/bin/obs2ioda_v3` não expõe uma interface de ajuda útil: `-h`, `--help` e `-help` terminam com sucesso sem explicar argumentos.

A execução testada é baseada no diretório corrente:

```text
<cycle-work-dir>/
  prepbufr.bufr -> <arquivo PREPBUFR de entrada>
```

O executável é chamado sem argumentos e procura o nome fixo `./prepbufr.bufr`. Os produtos IODA são escritos no mesmo diretório. O wrapper `scripts/obs2ioda/run_prepbufr.sh` cria ou verifica esse link de forma segura.

## Evidência de validação no JACI

### Tutorial NCAR: 2018-04-15 00 UTC

Entrada validada:

```text
external-inputs/mpasjedi_tutorial202509NCAR/obs_bufr/2018041500/
prepbufr.gdas.20180415.t00z.nr.48h
```

Produtos gerados e verificados com `ncdump -h`:

```text
sondes_obs_2018041500.h5
aircraft_obs_2018041500.h5
sfc_obs_2018041500.h5
satwind_obs_2018041500.h5
profiler_obs_2018041500.h5
ascat_obs_2018041500.h5
```

Todos continham os grupos `MetaData`, `ObsValue`, `ObsError` e `PreQC`.

### Operação: 2026-06-26 00 UTC

Entrada validada:

```text
/oper/dados/bdados/assimila/gdas/2026/06/26/inpe.t00z.prepbufr.nr
```

O conversor processou o PREPBUFR e produziu somente:

```text
sfc_obs_2026062600.h5
```

Esse resultado é válido: após o QC aplicado pelo conversor, o ciclo possuía observações de superfície, mas zero registros para sondagens, aeronaves e profiler. Por isso cada caso deve declarar explicitamente os produtos que ele precisa; não se deve exigir uma lista universal de coleções PREPBUFR.

## Perfis de configuração

- `examples/obs2ioda/prepbufr-tutorial/obs2ioda.yaml.example`: perfil estrito do tutorial, exigindo as seis coleções produzidas em 2018-04-15 00 UTC.
- `examples/obs2ioda/prepbufr-operational/obs2ioda.yaml.example`: perfil operacional que exige `sfc_obs_<YYYYMMDDHH>.h5`.
- `examples/obs2ioda/sondes/obs2ioda.yaml.example`: perfil que exige exclusivamente o produto de sondagens; ele falha de forma deliberada quando o PREPBUFR não contém sondagens.

## Uso do perfil operacional

```bash
mkdir -p cases/obs2ioda-operational
cp examples/obs2ioda/prepbufr-operational/obs2ioda.yaml.example \
  cases/obs2ioda-operational/obs2ioda.yaml
```

Substitua `USUARIO` no arquivo copiado e execute um ciclo conhecido:

```bash
source scripts/load_jaci_env.sh

monan-jedi-workflow obs2ioda-doctor cases/obs2ioda-operational \
  --cycle 2026-06-26T00:00:00Z

monan-jedi-workflow obs2ioda-prepare cases/obs2ioda-operational \
  --cycle 2026-06-26T00:00:00Z

monan-jedi-workflow obs2ioda-run cases/obs2ioda-operational \
  --cycle 2026-06-26T00:00:00Z

monan-jedi-workflow obs2ioda-validate cases/obs2ioda-operational \
  --cycle 2026-06-26T00:00:00Z
```

O manifest preserva o caminho de entrada, a configuração renderizada, o wrapper, as tentativas, os logs e os produtos validados.
