# Reconciliação da referência de setembro de 2025

## Resultado e limites

A referência concluída é `monan-jedi-20250901-7d`, de 01/09/2025 00Z a
08/09/2025 00Z. O relatório e a proveniência publicados registram 29 análises,
28 previsões entre ciclos, 29 conversões e 502 estados em sucesso.
A reconstrução publicada configura JEDI com 128 processos. Esses fatos não
substituem a inspeção da instalação e dos arquivos efetivamente usados.

Este procedimento coleta uma fotografia **atual** por leitura de arquivos.
Arquivos que mudaram após a execução não comprovam a versão histórica.
Datas de coleta, caminhos resolvidos, hashes e diferenças locais precisam
acompanhar qualquer atribuição de proveniência.

## Matriz de reconciliação

| Evidência | Estado conhecido | Conferência necessária |
|---|---|---|
| Código remoto | Inspecionado até `dc0ac5d5a2343ddab646bb2c82f3ad133c31eb34` | HEAD, branch, diferenças locais e caminho do pacote instalado na JACI |
| Receita publicada | `09a5ecb`: runtime M3, JEDI 128, outer/inner distintos | YAML e PBS materializados de todos os ciclos |
| Ambiente | Receita descreve PALS e endian GNU | Ambiente explícito dos PBS, executáveis resolvidos, hashes e builds |
| Produtos científicos | Diagnósticos de 29 análises publicados | Manifests originais, horários, malha/níveis, contratos de validação |
| Jobs | Jobs antigos com falha documentados | IDs e tentativas nos manifests da campanha concluída |
| Estado operacional | Resumo registra 502/502 estados em sucesso | Snapshot consistente do SQLite, separado dos manifests científicos |
| Logs | 29 caminhos e SHA-256 no resumo | Conferir hashes dos logs reais contra o resumo; conservar os logs na JACI |
| Dados fixos | Catálogo compartilhado conhecido | Versões/caminhos de B, malha, partições e tabelas físicas efetivamente usados |

## Coleta inicial na JACI

Execute em Bash no ambiente `monan-jedi`. Não é necessário fazer pull,
recriar o case ou chamar comandos de preparação/validação. O bloco escreve
apenas um novo diretório ao lado de `experiments/`, fora da campanha.

O pacote inclui arquivos regulares de configuração e manifestos com até 4 MiB
cada. Não segue links: seus caminhos e destinos são inventariados separadamente.
Não inclui NetCDF, BUFR, executáveis, SQLite ou logs completos. Fontes externas,
links e arquivos maiores precisam ser resolvidos no passo seguinte; esta coleta
inicial não é um snapshot científico completo.

```bash
(
  set -euo pipefail
  cd /p/projetos/monan_das/$USER/projects/monan-jedi-workflow
  repo_root="$PWD"
  campaign_root="$repo_root/experiments/2025-reference/cases/monan-jedi-20250901-7d"
  test -d "$campaign_root"
  snapshot_dir="$(mktemp -d "$repo_root/reconciliation-20261014.XXXXXX")"

  date -u +%FT%TZ > "$snapshot_dir/collected-at.txt"
  git rev-parse HEAD > "$snapshot_dir/git-head.txt"
  git branch --show-current > "$snapshot_dir/git-branch.txt"
  git status --short > "$snapshot_dir/git-status.txt"
  git diff --binary HEAD > "$snapshot_dir/git-worktree.patch"
  python --version > "$snapshot_dir/python-version.txt" 2>&1
  python -m pip list --format=json > "$snapshot_dir/packages-current.json"
  for executable in python monan-jedi-workflow swf; do
    command -v "$executable" >> "$snapshot_dir/commands-current.txt" || true
  done
  python -c 'import monan_jedi_workflow; print(monan_jedi_workflow.__file__)' \
    > "$snapshot_dir/package-location.txt"

  (
    cd "$campaign_root"
    find . -type l -printf '%p -> %l\n' > "$snapshot_dir/symlinks.txt"
    find . -type f \
      \( -name '*.yaml' -o -name '*.yml' -o -name '*.json' \
         -o -name '*.pbs' -o -name 'namelist.*' -o -name 'streams.*' \
         -o -name 'stream_list.*' -o -name 'COMPATIBILITY' \) \
      -size -4194305c -print0 > "$snapshot_dir/config-files.nul"
    xargs -0 -r sha256sum -- < "$snapshot_dir/config-files.nul" \
      > "$snapshot_dir/config-sha256.txt"
    tar --null --verbatim-files-from -czf "$snapshot_dir/campaign-configs.tar.gz" \
      -T "$snapshot_dir/config-files.nul"
  )

  tar -czf "$snapshot_dir.tar.gz" -C "$(dirname "$snapshot_dir")" \
    "$(basename "$snapshot_dir")"
  printf 'Coleta inicial: %s.tar.gz\n' "$snapshot_dir"
)
```

Nenhum executável científico é invocado. `prepare` pode recriar manifestos
ou limpar saídas; `validate` escreve relatórios. Não usar esses comandos
como ferramenta de captura. O script `capture_m3_reference.py` tem escopos
fixos de 2018 e não deve ser aplicado ao case de 2025 como se fosse genérico.

## Complemento e conferência

1. Resolver os links inventariados e arquivar os pequenos YAMLs, streams,
   namelists, PBS e listas de campos externos referenciados. Registrar também
   os links quebrados e arquivos excluídos por tamanho.
2. Arquivar os arquivos `campaign*.yaml` da origem e seus perfis/receitas
   referenciados, mantendo separados origem e conteúdo materializado.
3. Ler os PBS/manifestos para obter caminhos dos executáveis e seus checksums,
   instalação/build, módulos e setup declarados. Não capturar todo o ambiente
   ou executar os arquivos de setup para reconstruir retroativamente o ambiente.
4. Ler todos os manifests JEDI, MPAS, inicialização e OBS para produzir uma
   tabela ciclo/etapa/job/validação/entradas/saídas. Não inferir IDs de jobs
   a partir dos exemplos antigos do registro.
5. Conferir os 29 hashes de logs com `diagnostic_summary.json` publicado.
   Conservar os logs completos na JACI e registrar qualquer diferença.
6. Obter um backup consistente do SQLite com a API de backup do SQLite
   ou ferramenta equivalente em modo de leitura da origem. Não copiar o
   arquivo isoladamente enquanto houver escrita nem executar reset.
7. Conferir o modelo temporal: trajetória em T−3, estado completo em T,
   forecast externo fornece T+3/T+6 para o ciclo seguinte. Conferir
   `model.tstep` contra `config_dt` e física outer/forecast.
8. Comparar a captura com as referências publicadas e listar diferenças
   confirmadas, compatíveis e ainda sem explicação.

A captura atual e a evidência de execução são objetos distintos. Um arquivo
presente hoje somente integra a proveniência histórica quando está ligado
à tentativa executada por hash, manifesto, log ou outra evidência preservada.

## Critério para iniciar a migração

Registrar versões e divergências, localizar as configurações realmente usadas
e verificar a associação entre os manifests dos 29 ciclos e seus produtos.
Manter a campanha concluída como referência imutável. Mudanças arquiteturais
usam branch e diretório de experimento separados. O pacote inicial pode ser
analisado sem nova submissão de jobs.
