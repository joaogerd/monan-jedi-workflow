# Pipeline operacional Obs2IODA

O Obs2IODA é tratado como uma etapa independente de preparação de observações. Ele não depende do MPAS nem da execução MPAS-JEDI para converter e validar arquivos IODA. A integração com o caso de assimilação será feita depois, usando os produtos já validados.

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

A sequência esperada é:

```text
obs2ioda-doctor
  → confirma ferramentas e dependências do runtime linker

obs2ioda-prepare
  → resolve caminhos, confirma entradas e grava o plano imutável do ciclo

obs2ioda-run
  → executa conversores e preserva logs/proveniência

obs2ioda-validate
  → confere produtos, abre os arquivos com o inspecionador e exige marcas IODA
```

## Arquivo `obs2ioda.yaml`

O arquivo fica no diretório do caso ou experimento. A sintaxe concreta de cada conversor fica declarada em `argv`, porque ela depende do tipo de observação e da versão instalada do Obs2IODA.

```yaml
obs2ioda:
  # Um diretório isolado para cada ciclo.
  work_dir: build/obs2ioda/{cycle_id}

  # Caminhos de bibliotecas são configuráveis por site e aplicados somente aos
  # processos filhos deste stage. O ambiente global e os stages JEDI/MPAS não
  # são modificados.
  runtime:
    library_paths:
      - /site/obs2ioda/build/src
      - /site/obs2ioda/build/src/cxx
      - /site/libfabric/lib64
    dependency_checks:
      - /site/bin/obs2ioda_v3
    linker_command: ldd
    timeout_seconds: 30

  # Para arquivos IODA em NetCDF4/HDF5, ncdump costuma ser adequado.
  # O comando recebe o arquivo resolvido no placeholder {output}.
  inspection:
    argv: [ncdump, -h, "{output}"]
    timeout_seconds: 60
    required_header_markers:
      - MetaData
      - ObsValue
      - ObsError
      - PreQC

  # Ative somente quando o custo de hash para os arquivos for aceitável.
  provenance:
    sha256: false

  converters:
    - name: sondes
      inputs:
        - /dados/observacoes/sondes/{cycle_id}.bufr
      outputs:
        - "{work_dir}/sondes.nc4"
      timeout_seconds: 900
      argv:
        - /p/caminho/para/obs2ioda_v3
        # Completar com os argumentos validados para o conversor de sondagem.
        # Entradas e saídas podem usar {cycle_time}, {cycle_id} e {work_dir}.

    - name: gnssroref
      inputs:
        - /dados/observacoes/gnssro/{cycle_id}.bufr
      outputs:
        - "{work_dir}/gnssroref.nc4"
      argv:
        - /p/caminho/para/obs2ioda_v3
        # Completar com os argumentos validados para GNSS-RO.

    - name: surface
      inputs:
        - /dados/observacoes/surface/{cycle_id}.bufr
      outputs:
        - "{work_dir}/surface.nc4"
      argv:
        - /p/caminho/para/obs2ioda_v3
        # Completar com os argumentos validados para superfície.
```

## Placeholders disponíveis

```text
{cycle_time}      2018-04-15T00:00:00Z
{cycle_id}        20180415T000000Z
{mpas_time}       2018-04-15_00:00:00
{valid_time}      igual ao ciclo para Obs2IODA
{valid_id}        igual ao ciclo para Obs2IODA
{mpas_valid_time} formato MPAS do ciclo
{work_dir}        diretório isolado do ciclo Obs2IODA
```

## Produtos e proveniência

Para cada ciclo, os artefatos são armazenados em:

```text
build/obs2ioda/<cycle-id>/
  .monan-jedi-workflow/
    obs2ioda.json
    obs2ioda-doctor.json
    obs2ioda-validation.json
  logs/
    <conversor>.attempt-<n>.stdout.log
    <conversor>.attempt-<n>.stderr.log
    <conversor>.inspect-<n>.stdout.log
    <conversor>.inspect-<n>.stderr.log
```

O manifesto registra os argumentos efetivamente usados, a assinatura do plano, entradas, produtos, tentativas e, quando habilitado, hashes SHA-256.

## Contrato de dependências compartilhadas

`runtime.library_paths` é materializado como um `LD_LIBRARY_PATH` prefixado
somente no ambiente dos probes, conversores e inspetores Obs2IODA. O processo
do workflow não altera `os.environ`; por isso essa configuração não alcança
PBS, JEDI ou MPAS. Os paths podem usar as mesmas variáveis e placeholders do
restante do caso e não dependem de um ciclo específico.

Cada item de `runtime.dependency_checks` identifica um ELF que deve ser
auditado. `obs2ioda-doctor` executa o `linker_command` (por padrão, `ldd`) no
ambiente materializado e registra o executável, as bibliotecas resolvidas e as
bibliotecas ausentes em `obs2ioda-doctor.json`. Qualquer `not found` torna o
doctor inválido. `obs2ioda-run` repete a verificação imediatamente antes dos
conversores, grava o resultado no manifesto e falha com
`failed-runtime-dependencies` antes de criar produtos quando a resolução não é
completa. Assim, o erro é diagnosticado antes de chegar a `error while loading
shared libraries`.

Um executável instalado corretamente pode usar `$ORIGIN` no seu RPATH e não
precisar de `library_paths`. Binários de build tree ou dependências
deliberadamente fornecidas pelo ambiente do site devem declará-los no caso. A
configuração é local ao Obs2IODA; não se deve exportar `LD_LIBRARY_PATH`
globalmente.

No binário JACI auditado, o ELF contém `DT_RPATH`, não `DT_RUNPATH`, e aponta
para uma build tree antiga `monan-jedi-mpas/obs2ioda`. A build atual produz
`libv3.so` em `build/src` e `libobs2ioda_cxx.so` em `build/src/cxx`;
`libfabric.so.1` chega transitivamente pela pilha paralela e é fornecida pelo
site. O CMake do Obs2IODA define um `INSTALL_RPATH` relocável baseado em
`$ORIGIN`, mas o executável publicado foi copiado da build tree, não de um
layout instalado com suas bibliotecas. Por isso a solução operacional é o
runtime local ao stage; publicar um bundle instalado e relocável continua
sendo a correção estrutural de build recomendada.

## Reuso e correção

- `obs2ioda-run` pula um conversor quando todas as saídas declaradas já existem e não estão vazias.
- `obs2ioda-run --force` reexecuta os conversores mesmo com produtos existentes.
- `obs2ioda-prepare --refresh` substitui um plano não concluído após uma correção de configuração.
- Um plano que já terminou com sucesso não é sobrescrito automaticamente quando a configuração muda; isso evita associar produtos antigos a uma configuração nova sem uma decisão explícita.

## Limite atual

A validação estrutural usa o comando configurado em `inspection.argv`; com `ncdump -h`, ela exige a presença dos grupos e campos textuais declarados. A validação científica específica de cada tipo observacional — faixas físicas, unidades, canais, cobertura espacial e temporal — será acrescentada por conversor quando os contratos de sondagem, GNSS-RO e superfície forem definidos e testados no JACI.
