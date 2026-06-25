# Caso de referência Obs2IODA: sondagens

Este diretório contém o contrato de configuração para iniciar a conversão de sondagens por ciclo. Ele é independente de MPAS e MPAS-JEDI; os arquivos IODA validados poderão ser usados mais tarde pelo caso de assimilação.

## Preparação

Copie o template sem alterar o original:

```bash
cp examples/obs2ioda/sondes/obs2ioda.yaml.example \
  cases/obs2ioda-sondes/obs2ioda.yaml
```

Edite os campos em `variables`:

- `obs2ioda_executable`: binário publicado pelo bundle MONAN-JEDI;
- `ncdump_executable`: normalmente `ncdump` no ambiente carregado;
- `sonde_converter`: wrapper cuja chamada ao Obs2IODA já tenha sido comprovada no JACI;
- `sonde_input_root`: catálogo de BUFR das sondagens;
- `output_root`: área de trabalho e produtos IODA.

O wrapper recebe, neste exemplo:

```text
--input  <arquivo BUFR>
--output <arquivo IODA>
```

Esse contrato é do nosso caso de workflow. Dentro do wrapper fica a interface específica da versão instalada do Obs2IODA, evitando espalhar comandos experimentais pelo YAML ou pelo `simpleWorkflow`.

## Primeiro ciclo de validação

Use um único horário que tenha BUFR conhecido:

```bash
monan-jedi-workflow obs2ioda-doctor cases/obs2ioda-sondes \
  --cycle 2018-04-15T00:00:00Z

monan-jedi-workflow obs2ioda-prepare cases/obs2ioda-sondes \
  --cycle 2018-04-15T00:00:00Z

monan-jedi-workflow obs2ioda-run cases/obs2ioda-sondes \
  --cycle 2018-04-15T00:00:00Z

monan-jedi-workflow obs2ioda-validate cases/obs2ioda-sondes \
  --cycle 2018-04-15T00:00:00Z
```

A validação inicial exige que o arquivo seja não vazio e que `ncdump -h` encontre os grupos `MetaData`, `ObsValue`, `ObsError` e `PreQC`.

## Produtos

```text
<output_root>/20180415T000000Z/
  sondes.nc4
  .monan-jedi-workflow/
    obs2ioda-doctor.json
    obs2ioda.json
    obs2ioda-validation.json
  logs/
```

O manifest registra a configuração renderizada, argumentos, entradas, saídas, tentativas e logs. Ative `provenance.sha256: true` quando a rastreabilidade integral dos arquivos justificar o custo de leitura.
