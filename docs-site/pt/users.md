# Documentação para usuários

## Funcionamento simples

O usuário prepara o ambiente, disponibiliza os arquivos científicos reais, roda validações e só depois submete o job PBS.

O workflow foi desenhado para evitar submissões caras com erro simples de configuração.

## Passo a passo resumido

```bash
source scripts/env/load_jaci_env.sh configs/sites/jaci/site.env
bash tests/smoke_check.sh
bash scripts/setup/create_3dvar_fgat_external_tree.sh
bash scripts/setup/stage_3dvar_fgat_inputs.sh --dry-run
bash scripts/setup/stage_3dvar_fgat_inputs.sh
bash scripts/setup/validate_3dvar_fgat_staged_inputs.sh
bash scripts/run/render_3dvar_fgat.sh
bash scripts/run/prepare_3dvar_fgat_runtime.sh --strict
bash scripts/run/render_3dvar_fgat_pbs.sh
qsub build/rendered/3dvar_fgat.pbs
```

## Entradas esperadas

- background MPAS;
- arquivos IODA;
- covariância SABER/BUMP;
- graph info;
- arquivo estático;
- build MPAS-JEDI.

## Saídas esperadas

- YAML JEDI renderizado;
- observers renderizados;
- runtime preparado;
- job PBS renderizado;
- logs da execução;
- análise JEDI;
- feedback/diagnósticos de observação.

## Perguntas frequentes

### Preciso saber Cylc para usar o sistema?

Não na fase atual. Os comandos de alto nível são scripts Bash. Uma camada Cylc ou ecFlow pode ser adicionada depois.

### Posso usar scripts do grupo MONAN para forecast?

Sim. O desenho recomendado é usar wrappers para chamar esses scripts, preservando o contrato de entrada e saída.

### O que acontece se os arquivos IODA não existirem?

As validações avisam ou falham, dependendo do modo usado. Use modo permissivo durante preparação e modo estrito antes de submeter PBS.
