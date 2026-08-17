# Reproduzir primeiro o `baseline_bmatrix`

Antes de configurar o ciclo completo, reproduza **uma unica analise JEDI que ja sabemos funcionar**. Isso separa problemas do novo stage de problemas de Obs2IODA, forecast MPAS e orquestracao.

Neste teste use exatamente o mesmo executavel, YAML, background, observacoes e B do `baseline_bmatrix`.

**Nao edite `obs2ioda.yaml`, `mpas.yaml` ou `workflow.yaml` ainda.**

## 1. Defina os diretorios

```bash
export CASE=/p/projetos/monan_das/$USER/work/CASE
export BASELINE=/p/projetos/monan_das/$USER/manual-tests/baseline_bmatrix
mkdir -p "$CASE"
```

Confirme as entradas:

```bash
test -f "$BASELINE/variants/3dfgat.bmatrix.yaml"
test -f "$BASELINE/Data/background/2018041500/mpasout.2018-04-14_21.00.00.nc"
test -f "$BASELINE/Data/ufo/sondes_obs_2018041500_m.nc4"
test -f "$BASELINE/Data/ufo/gnssro_obs_2018041500_s.nc4"
test -f "$BASELINE/Data/ufo/sfc_obs_2018041500_m.nc4"
test -d "$BASELINE/Data/covariance"
```

## 2. Crie um runtime skeleton limpo

Preserve os arquivos fixos do baseline, mas nao copie as entradas/produtos que o stage vai materializar explicitamente:

```bash
rm -rf "$CASE/runtime-skeleton"
mkdir -p "$CASE/runtime-skeleton"

rsync -a \
  --exclude 'variants/' \
  --exclude 'Data/background/' \
  --exclude 'Data/ufo/' \
  --exclude 'Data/os/' \
  --exclude 'Data/states/' \
  --exclude 'Data/covariance/' \
  --exclude '.monan-jedi-workflow/' \
  "$BASELINE/" "$CASE/runtime-skeleton/"

mkdir -p \
  "$CASE/runtime-skeleton/Data/background" \
  "$CASE/runtime-skeleton/Data/ufo" \
  "$CASE/runtime-skeleton/Data/os" \
  "$CASE/runtime-skeleton/Data/states"
```

Assim `geometry/2018041500` e os demais assets fixos continuam identicos ao baseline, enquanto B, background e observacoes entram por links explicitos.

## 3. Crie somente o `jedi.yaml`

```bash
cp \
  /p/projetos/monan_das/$USER/projects/monan-jedi-workflow/examples/simpleworkflow/cycled_da/jedi-baseline-bmatrix.yaml.example \
  "$CASE/jedi.yaml"
```

Edite `USUARIO` e o caminho `current_install`.

Para descobrir o executavel atual:

```bash
command -v mpasjedi_variational.x
readlink -f "$(command -v mpasjedi_variational.x)"
```

Se o executavel estiver em `/algum/prefixo/bin/mpasjedi_variational.x`, use `/algum/prefixo` como `current_install`.

Nesta primeira reproducao, `templates.source` aponta diretamente para:

```text
$BASELINE/variants/3dfgat.bmatrix.yaml
```

Portanto o YAML cientifico ainda nao e convertido em template ciclico.

## 4. Prepare sem submeter

```bash
monan-jedi-workflow jedi-prepare "$CASE" \
  --cycle 2018-04-15T00:00:00Z
```

Esse comando nao chama `qsub`.

Confira:

```bash
RUN="$CASE/work/jedi/20180415T000000Z"

ls -l "$RUN/Data/background/2018041500"
ls -l "$RUN/Data/ufo"
ls -ld "$RUN/Data/covariance"
diff -u \
  "$BASELINE/variants/3dfgat.bmatrix.yaml" \
  "$RUN/3dfgat.bmatrix.yaml"
cat "$RUN/run_jedi.pbs"
```

O `diff` deve produzir **nenhuma diferenca**.

O runtime deve conter, entre outros:

```text
work/jedi/20180415T000000Z/
  3dfgat.bmatrix.yaml
  run_jedi.pbs
  geometry/2018041500/...
  Data/background/2018041500/mpasout.2018-04-14_21.00.00.nc
  Data/covariance -> baseline/Data/covariance
  Data/ufo/sondes_obs_2018041500_m.nc4
  Data/ufo/gnssro_obs_2018041500_s.nc4
  Data/ufo/sfc_obs_2018041500_m.nc4
  .monan-jedi-workflow/
```

## 5. Submeta e valide

```bash
monan-jedi-workflow jedi-submit "$CASE" \
  --cycle 2018-04-15T00:00:00Z

monan-jedi-workflow jedi-wait "$CASE" \
  --cycle 2018-04-15T00:00:00Z \
  --poll-seconds 30

monan-jedi-workflow jedi-validate "$CASE" \
  --cycle 2018-04-15T00:00:00Z
```

O produto esperado pelo `baseline_bmatrix` e:

```text
Data/states/mpas.3dvar.2018-04-15_00.00.00.nc
```

## 6. Somente depois que esse teste passar

A evolucao deve ser incremental:

1. transformar `3dfgat.bmatrix.yaml` em template realmente ciclico;
2. substituir Radiosonde/Sfc pelos produtos do Obs2IODA;
3. fornecer GNSSRO por ciclo;
4. fazer a analise inicializar o MPAS;
5. validar o background de 03Z;
6. fazer a analise de 06Z;
7. por ultimo executar essa mesma sequencia com `simpleWorkflow`.

Cada passo muda apenas uma parte do baseline conhecido.
