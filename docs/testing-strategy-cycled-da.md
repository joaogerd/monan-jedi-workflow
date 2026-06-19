# Estratégia de testes incrementais — Ciclo de AD MONAN-JEDI

## Regra do projeto

Nenhuma funcionalidade nova é considerada concluída apenas porque foi escrita.
Cada passo deve ter:

1. uma entrada controlada;
2. uma saída observável;
3. uma verificação automática ou checklist objetivo;
4. um critério claro de aprovação;
5. um teste de regressão quando corrigir um problema encontrado.

A sequência de validação deve ir do mais barato para o mais caro:

```text
unitário local
  -> integração local sem MPAS/JEDI
  -> renderização e comparação com baseline
  -> preparação de runtime no JACI
  -> smoke test PBS/MPAS/JEDI
  -> ciclo de dois tempos
  -> dia, semana, mês
```

Nenhuma etapa HPC deve ser usada para descobrir erros simples de datas, YAML,
paths, composição, dependências ou templates.

## Pirâmide de testes

### 1. Testes unitários Python

Objetivo: validar funções puras sem filesystem, JACI, MPAS ou JEDI.

Exemplos:

- conversão de datas UTC;
- geração de `cycle_id`;
- cálculo de janela e trajetória FGAT;
- cálculo de leads e duração do forecast;
- validação de offsets ordenados;
- resolução de caminhos temporais;
- composição de configurações e precedência de overrides;
- validação de referências de componentes.

Comando:

```bash
python -m pytest tests/test_timeline.py
```

Critério: testes rápidos, determinísticos e executáveis em qualquer máquina com
Python suportado.

### 2. Testes de integração local

Objetivo: exercitar várias camadas do workflow usando diretórios temporários e
arquivos pequenos artificiais.

Exemplos:

- um experimento mínimo resolve método, geometria, B matrix, observações,
  forecast e plataforma;
- o resolvedor gera `resolved-config.yaml`;
- a preparação cria o layout runtime esperado;
- a operação é idempotente;
- referências inexistentes falham com mensagem clara;
- um ciclo de dois tempos cria dependências corretas sem executar MPAS.

Critério: não exigir arquivos científicos reais, binários ou JACI.

### 3. Testes de equivalência do baseline

Objetivo: garantir que a nova arquitetura não altera o caso validado.

Para o baseline `3dfgat_mpastatic_x1.10242_2018041500`, comparar:

- campos críticos do YAML JEDI renderizado;
- ordem de variáveis e observadores;
- caminhos renderizados;
- tempo de análise, tempos da trajetória FGAT e janela;
- conteúdo essencial do PBS;
- arquivos/links esperados no runtime.

A comparação deve ser estrutural para YAML, e por blocos/linhas relevantes para
PBS e arquivos MPAS. Não comparar texto bruto quando diferenças inofensivas de
formatação puderem causar falso negativo.

Critério: o baseline novo é semanticamente equivalente ao manual antes de
migrar qualquer execução real.

### 4. Testes de preparação no JACI

Objetivo: verificar que paths, links, permissões, módulos e arquivos reais
existem no ambiente de execução.

Sem submeter jobs, validar:

- links simbólicos;
- `xtime` dos arquivos MPAS requeridos;
- presença dos arquivos de física;
- partição compatível com `run.tasks`;
- executável MPAS-JEDI acessível;
- matriz B e metadados compatíveis;
- arquivos de observação disponíveis para a janela.

Comando desejado:

```bash
monan-jedi-workflow cycle doctor EXPERIMENT.yaml --time 2018041500
```

Critério: falha antecipada e explicativa antes de gerar PBS ou ocupar fila.

### 5. Smoke tests PBS

Objetivo: validar o script e o ambiente real com custo controlado.

Primeiro smoke test:

- renderizar PBS;
- submeter manualmente um job curto;
- carregar módulos;
- entrar no diretório runtime;
- verificar variáveis e executáveis;
- validar que o job enxerga arquivos necessários;
- não executar ainda uma assimilação completa, quando possível.

Segundo smoke test:

- executar o menor caso MPAS/JEDI que ainda testa o caminho real;
- confirmar criação de logs e saída esperada;
- extrair erros de inicialização e I/O.

Critério: cada alteração de PBS, módulos, paths ou staging deve ter smoke test
antes de ser usada em ciclo completo.

### 6. Testes científicos/operacionais por escala

| Escala | Objetivo de teste | Critério de passagem |
|---|---|---|
| Caso único | reproduzir baseline | YAML/PBS/runtime equivalentes e execução válida |
| Dois tempos | testar encadeamento | forecast do primeiro ciclo satisfaz trajetória do segundo |
| Um dia | testar quatro ciclos | nenhum ajuste manual em arquivos runtime |
| Uma semana | testar retomada e estabilidade | falhas recuperáveis e manifestos consistentes |
| Um mês | testar robustez e diagnóstico | estatísticas e produtos completos |
| Contínuo | testar operação | reinício seguro, rastreabilidade e monitoramento |

## Checklist obrigatório por Pull Request

Todo PR que mexer em comportamento deve declarar:

```text
[ ] Qual comportamento foi adicionado ou alterado?
[ ] Qual teste unitário cobre a regra nova?
[ ] Qual teste de regressão protege o baseline, quando aplicável?
[ ] Qual comando local foi executado?
[ ] Há impacto em YAML renderizado, PBS, runtime ou dados?
[ ] Há necessidade de smoke test JACI?
[ ] Qual é o critério objetivo para considerar a mudança aprovada?
```

## Política para problemas encontrados

Quando um passo falhar:

1. preservar logs, YAML/PBS renderizados e `manifest.yaml`;
2. reduzir o problema ao menor caso reproduzível;
3. criar um teste que falha antes da correção;
4. corrigir o código/configuração;
5. confirmar que o teste novo passa e que os anteriores continuam passando;
6. somente então repetir o teste mais caro no JACI.

## Primeiros testes obrigatórios

A próxima funcionalidade, `cycle plan`, deve ter estes testes antes de virar CLI:

1. plano de uma análise 00Z com trajetória `[-3, 0, +3]`;
2. plano de um dia com quatro análises;
3. verificação de que 00Z usa forecast iniciado em 18Z e 06Z usa forecast
   iniciado em 00Z;
4. offsets e intervalo inválidos produzem erro claro;
5. saída do plano é estável e não cria arquivos.
