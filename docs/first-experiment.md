# Primeiro experimento real: instalação → execução

Esta receita fixa usa x1.10242 (~240 km), 55 níveis, B correspondente, 128 ranks,
3D-FGAT, análises em 01/09/2025 00Z e 06Z. É um exemplo científico instalado,
não uma restrição do software a essa resolução. Não requer uma campanha antiga.

## 1. Instalar a entrega

Extraia o pacote novo em um diretório novo em `/p`. No ambiente MONAN-JEDI,
instale a pasta extraída:

```bash
python -m pip install --no-deps --no-build-isolation -e /CAMINHO/monan-jedi-workflow
python -m monan_jedi_workflow.experiment_start --help
```

`/CAMINHO` é a única localização da instalação escolhida por você. As dependências
Python (PyYAML, NumPy, netCDF4) e os executáveis MONAN-JEDI/MPAS/WPS/Obs2IODA
precisam estar instalados. O ambiente Python deve ser acessível nos compute nodes;
um ambiente em `/home2` precisa ser testado ou recriado em `/p` antes de submeter.

## 2. Declarar ambiente e dados

Na JACI de João, use os caminhos abaixo; outros usuários apontam para suas
instalações e conjuntos de dados equivalentes. Caminhos são configuração,
não dados baixados automaticamente pela plataforma.

```bash
export STACK_ROOT=/p/projetos/monan_das/joao.gerd/work/spack-stack-inpe-overlay-20260515T181917Z/spack-stack
export MONAN_JEDI_INSTALL_ROOT=/p/projetos/monan_das/$USER/build/monan-jedi
export MONAN_MESH_ROOT=/p/projetos/monan_das/share/MONAN-JEDI-Data/meshes/quasi_uniform/x1.10242_240km
export MONAN_PHYSICS_ROOT=/p/projetos/monan_das/share/MONAN-JEDI-Data/physics/mpas/files
export MONAN_BMATRIX_ROOT=/p/projetos/monan_das/share/MONAN-JEDI-Data/covariance/x1.10242_240km/55levels
export MONAN_LIBFABRIC_ROOT=/opt/cray/libfabric/1.22.0/lib64
export MONAN_INPUT_ROOT=/p/projetos/monan_das/$USER/external-inputs
export MONAN_GFS_ROOT=/p/projetos/monan_das/$USER/data/gfs
export NEW_CASE=/p/projetos/monan_das/$USER/work/first-experiment-20250901
```

Inventário obrigatório antes da execução:

| Insumo | Local relativo à raiz declarada | Origem |
|---|---|---|
| Malha estática | `$MONAN_MESH_ROOT/static/x1.10242.invariant.nc` | Assets MONAN-JEDI-Data |
| Partição MPI | `$MONAN_MESH_ROOT/partitions/x1.10242.graph.info.part.128` | Assets da mesma malha, 128 ranks |
| Física | `$MONAN_PHYSICS_ROOT` | Tabelas MPAS da instalação científica |
| Matriz B | `$MONAN_BMATRIX_ROOT` | HDIAG/NICAS e demais produtos B compatíveis |
| Análise GFS | `$MONAN_GFS_ROOT/2025083118/gfs.t18z.pgrb2.0p25.f000` | Arquivo histórico GFS 31/08/2025 18Z |
| PREPBUFR 00Z | `$MONAN_INPUT_ROOT/observations/prepnr/2025/prepbufr.gdas.2025090100.nr` | Arquivo histórico PREPBUFR |
| PREPBUFR 06Z | Mesmo diretório, `prepbufr.gdas.2025090106.nr` | Arquivo histórico PREPBUFR |
| GNSS-RO 00Z | `$MONAN_INPUT_ROOT/observations/gpsro/2025/gdas.gpsro.t00z.20250901.bufr` | Arquivo histórico GNSS-RO |
| GNSS-RO 06Z | Mesmo diretório, `gdas.gpsro.t06z.20250901.bufr` | Arquivo histórico GNSS-RO |

O pacote fornece as configurações, templates e wrappers, não esses dados grandes
nem a matriz B. Esta receita não implementa download das observações históricas.
Se faltarem insumos, provisioná-los do acervo institucional antes de executar;
não substituir por arquivos de outra data ou por produtos artificiais. Acesso
público atual aos arquivos históricos ainda precisa ser verificado antes de
oferecer instruções de aquisição automática a usuários externos.

## 3. Criar o caso

```bash
python -m monan_jedi_workflow.experiment_start "$NEW_CASE"
cd "$NEW_CASE"
```

Saídas: `experiment.yaml`, `initialization.yaml`, `init.yaml`, `science/` com
configurações completas e `run-case.pbs`. O criador recusa sobrescrever diretórios.
Não informar `REFERENCE_CASE` nem procurar `jedi.yaml` de campanhas antigas.

## 4. Conferir entradas antes de gastar uma alocação

```bash
test -r "$MONAN_GFS_ROOT/2025083118/gfs.t18z.pgrb2.0p25.f000"
test -r "$MONAN_JEDI_INSTALL_ROOT/share/monan-jedi/install-manifest.json"
obs convert check experiment.yaml --cycle 2025-09-01T00:00:00Z
obs convert check experiment.yaml --cycle 2025-09-01T06:00:00Z
jedi inspect experiment.yaml --cycle 2025-09-01T00:00:00Z
mpas inspect initialization.yaml --cycle 2025-08-31T18:00:00Z
```

Cada comando precisa terminar com status zero. `test` não imprime mensagem em
sucesso. `inspect` mostra caminhos sem exigir estados futuros já produzidos.
O manifesto de instalação deve ser verdadeiro e compatível com o contrato v2.
O shell também chama check/prepare/validate em cada etapa. Confira fila, tempo e
recursos de `run-case.pbs`; os valores fornecidos são PBS/JACI, um nó e 128 ranks.

## 5. Executar o shell explícito

```bash
qsub run-case.pbs
```

A sequência contida no shell é:

1. WPS/ungrib da análise GFS de 31/08 18Z.
2. `mpas init` no mesmo instante: interpolação para a malha do experimento.
3. `mpas` sem DA por seis horas: produz estados às 21Z e 00Z.
4. `obs convert` em 01/09 00Z e `jedi` 00Z.
5. `mpas` a partir da análise 00Z: produz estados às 03Z e 06Z.
6. `obs convert` em 06Z e `jedi` 06Z.

A trajetória da primeira assimilação é o estado de 21Z; seu estado completo é
o de 00Z. A segunda usa trajetória de 03Z e estado completo de 06Z produzidos
pelo próprio candidato. As ligações são criadas antes da execução e estarão
pendentes até o produtor terminar. Nenhum resultado antigo é utilizado.

WPS usa comandos legados por ainda não ter app independente. Os demais usam
os verbos comuns check/prepare/run/validate. Cada app executa somente uma etapa;
o encadeamento pertence a este shell explícito do usuário. Não executar o shell
no login nem rodar outro orquestrador sobre o mesmo diretório simultaneamente.

## 6. Conferir resultado e produzir diagnóstico

```bash
jedi status experiment.yaml --cycle 2025-09-01T06:00:00Z
python -m monan_jedi_workflow.scientific_feedback \
  work/jedi/20250901T000000Z/Data/os/obsout_3dvar_sondes.nc4
python -m monan_jedi_workflow.scientific_feedback \
  work/jedi/20250901T060000Z/Data/os/obsout_3dvar_sondes.nc4
```

Esperado: duas análises validadas, previsões inicial e intermediária validadas,
IODA dos dois horários e estatísticas pareadas de sondas. Logs gerais:
`case.stdout.log` e `case.stderr.log`; logs nativos dentro de cada runtime.
A primeira falha interrompe o shell. Envie esses logs antes de tentar novamente;
a receita não oferece retomada automática do shell PBS.

Isso comprova funcionamento e permite avaliar os resultados. Equivalência com
a referência e reprodutibilidade independente continuam sendo verificações
separadas, exigidas pelo planejamento científico do GAD.
