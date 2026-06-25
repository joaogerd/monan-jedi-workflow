# Pipeline operacional Obs2IODA

O Obs2IODA é uma etapa independente de preparação de observações. Ele não depende de MPAS ou MPAS-JEDI para converter e validar produtos IODA. O caso de assimilação poderá consumi-los depois de validados.

## Comandos

```bash
monan-jedi-workflow obs2ioda-doctor CONFIG_DIR \
  --cycle 2018-04-15T00:00:00Z

monan-jedi-workflow obs2ioda-prepare CONFIG_DIR \
  --cycle 2018-04-15T00:00:00Z

monan-jedi-workflow obs2ioda-run CONFIG_DIR \
  --cycle 2018-04-15T00:00:00Z

monan-jedi-workflow obs2ioda-validate CONFIG_DIR \
  --cycle 2018-04-15T00:00:00Z
```

A sequência é:

```text
obs2ioda-doctor
  → verifica executáveis e executa probes explicitamente configurados

obs2ioda-prepare
  → resolve variáveis, caminhos e entradas; grava plano imutável do ciclo

obs2ioda-run
  → executa conversores e preserva logs/proveniência

obs2ioda-validate
  → abre os produtos com o inspecionador e exige marcas IODA
```

## Arquivo `obs2ioda.yaml`

A sintaxe concreta de cada conversor permanece em `argv`, pois ela depende do tipo observacional e da versão instalada do Obs2IODA. O pipeline não embute comandos observacionais fictícios.

```yaml
obs2ioda:
  # Variáveis de caminho podem usar os campos temporais abaixo e variáveis
  # declaradas anteriormente no mesmo bloco.
  variables:
    obs2ioda_executable: /p/caminho/obs2ioda_v3
    ncdump_executable: ncdump
    sonde_converter: /p/caminho/convert_sondes.sh
    sonde_input_root: /dados/observacoes/sondes
    output_root: /dados/trabalho/obs2ioda

  work_dir: "{output_root}/{cycle_id}"

  # Somente configure probes cuja interface foi confirmada no ambiente.
  probes:
    - name: obs2ioda-interface
      argv: ["{obs2ioda_executable}", "--help"]
      required_output_markers: []
      timeout_seconds: 30

  inspection:
    argv: ["{ncdump_executable}", -h, "{output}"]
    timeout_seconds: 60
    required_header_markers:
      - MetaData
      - ObsValue
      - ObsError
      - PreQC

  provenance:
    sha256: false

  converters:
    - name: sondes
      inputs:
        - "{sonde_input_root}/{cycle_id}.bufr"
      outputs:
        - "{work_dir}/sondes.nc4"
      timeout_seconds: 900
      argv:
        - "{sonde_converter}"
        - --input
        - "{sonde_input_root}/{cycle_id}.bufr"
        - --output
        - "{work_dir}/sondes.nc4"
```

## Variáveis e placeholders

`variables` é renderizado na ordem declarada. Cada variável pode referenciar os campos temporais ou variáveis anteriores. Ela não pode substituir campos reservados, como `cycle_id` e `work_dir`.

```text
{cycle_time}      2018-04-15T00:00:00Z
{cycle_id}        20180415T000000Z
{mpas_time}       2018-04-15_00:00:00
{valid_time}      igual ao ciclo para Obs2IODA
{valid_id}        igual ao ciclo para Obs2IODA
{mpas_valid_time} formato MPAS do ciclo
{work_dir}        diretório isolado do ciclo Obs2IODA
```

Durante a inspeção, `{output}` também representa o produto IODA específico que está sendo validado.

## Probes

O `doctor` já confirma que o primeiro elemento de cada `argv` é um executável disponível. Probes são verificações adicionais e opcionais: o caso declara exatamente o comando, o tempo máximo e eventuais marcadores esperados no resultado.

Assim, por exemplo, `--help`, `--version` ou um comando de teste da instalação só são usados quando já foram confirmados para a versão publicada no JACI.

## Produtos e proveniência

Para cada ciclo:

```text
<work_dir>/
  .monan-jedi-workflow/
    obs2ioda.json
    obs2ioda-doctor.json
    obs2ioda-validation.json
  logs/
    doctor-<probe>.stdout.log
    doctor-<probe>.stderr.log
    <conversor>.attempt-<n>.stdout.log
    <conversor>.attempt-<n>.stderr.log
    <conversor>.inspect-<n>.stdout.log
    <conversor>.inspect-<n>.stderr.log
```

O manifesto registra a assinatura do plano, argumentos renderizados, entradas, produtos, tentativas e, quando habilitado, hashes SHA-256.

## Reuso e correção

- `obs2ioda-run` pula conversores cujas saídas declaradas já existam e não estejam vazias.
- `obs2ioda-run --force` reexecuta os conversores.
- `obs2ioda-prepare --refresh` só pode substituir um plano que ainda não gerou produtos convertidos ou validados.
- Um plano alterado não pode substituir silenciosamente produtos já convertidos: use novo `output_root` ou uma versão explícita para preservar a proveniência.

## Limite atual

A validação estrutural usa o comando em `inspection.argv`; com `ncdump -h`, ela exige grupos e marcadores textuais declarados. A validação científica por tipo observacional — unidades, cobertura temporal, faixa física, canais ou variáveis — será acrescentada quando os contratos de sondagem, GNSS-RO e superfície forem confirmados no JACI.
