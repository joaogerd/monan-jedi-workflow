# Contributing

O objetivo deste projeto não é apenas produzir código que funcione; é produzir um workflow científico que outra pessoa consiga **usar, compreender, depurar e transferir para operação**.

## Regras arquiteturais

1. `monan-jedi-workflow` implementa lógica de domínio, não o workflow completo de produção.
2. Nenhum módulo de domínio deve depender de `simpleWorkflow`, ecFlow ou Cylc.
3. Etapas cíclicas devem possuir contratos explícitos e, quando aplicável, operações separadas de preparação, execução/submissão, espera e validação.
4. Término do scheduler não substitui validação científica.
5. A matriz B é um artefato externo à campanha cíclica.
6. No estágio JEDI, `cycle_time` representa o horário da análise.
7. Não esconda `qsub`, MPI ou outra ação cara dentro de um comando que pareça somente validar/preparar.

Consulte `docs/developer/adr/` antes de alterar uma dessas decisões.

## Fluxo de desenvolvimento

```bash
git switch main
git pull --ff-only
git switch -c feature/minha-mudanca
python -m pytest
```

Mudanças devem ser pequenas o suficiente para revisão, mas completas o suficiente para deixar documentação e testes consistentes.

## Definition of Done

Uma mudança que altera comportamento público só está pronta quando inclui, conforme aplicável:

- implementação;
- testes de sucesso;
- testes dos principais modos de falha;
- atualização da CLI/`--help`;
- documentação curta para o usuário;
- documentação detalhada para o desenvolvedor;
- docstrings públicas;
- exemplo/template;
- ADR quando uma decisão arquitetural nova foi tomada;
- comportamento de reexecução/restart documentado e testado.

Não deixe documentação para uma etapa futura da feature.

## Padrão de documentação no código

Módulos importantes devem explicar:

- responsabilidade;
- o que deliberadamente não fazem;
- modelo conceitual;
- entradas e saídas;
- invariantes;
- efeitos colaterais;
- idempotência/restart;
- decisões não óbvias;
- principais falhas esperadas.

Comentários inline devem explicar principalmente **por que** uma escolha existe. Não escreva comentários que apenas traduzem a próxima linha de Python para português/inglês.

## Contratos de filesystem

Arquivos produzidos entre etapas devem ter nomes/paths determinísticos e ser validados antes de consumo. Manifests pequenos em JSON são preferíveis quando ajudam a publicar semanticamente produtos (`analysis`, `background`, etc.) sem obrigar outro componente a interpretar logs.

Não versione NetCDF/HDF5/GRIB/BUFR grandes, diretórios de runtime ou logs científicos.

## Segurança de reexecução

Uma etapa deve declarar claramente se é idempotente. Em particular:

- links simbólicos válidos podem ser reutilizados;
- arquivos reais de usuário não devem ser sobrescritos silenciosamente;
- submissões PBS existentes devem ser reutilizadas por padrão;
- reenvio precisa ser explícito (`--resubmit` quando suportado);
- diretórios já preparados não podem misturar silenciosamente assets de baselines incompatíveis.

## Testes

Suíte principal:

```bash
python -m pytest
```

Quando alterar CLI, modelos temporais ou contratos de stage, inclua testes unitários que não dependam do JACI. Testes reais no JACI complementam, mas não substituem, os testes locais de contrato.

## PRs

Títulos recomendados:

```text
feat: add cycle-aware JEDI stage
test: cover analysis/forecast handoff
docs: document orchestration boundary
fix: preserve validated runtime assets
```

O corpo do PR deve registrar:

- o que mudou;
- por que mudou;
- impacto para usuário/desenvolvedor;
- testes executados;
- o que ainda requer validação no JACI.
