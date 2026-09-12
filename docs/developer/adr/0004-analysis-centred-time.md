# ADR 0004 — Horário do ciclo é o horário da análise

**Status:** accepted

## Contexto

Em 3D-FGAT coexistem horários de análise, background, início/fim de janela, inicialização da previsão e próximo background. Usar a palavra `cycle` para diferentes instantes gerou ambiguidade em protótipos anteriores.

## Decisão

No estágio JEDI, `cycle_time` significa sempre o horário da análise. Outros instantes são derivados por parâmetros explícitos (`step_hours`, `background_offset_hours`, `window_hours`).

## Consequências

- nomes de arquivos podem ser renderizados deterministicamente;
- a lógica temporal não fica espalhada por shell/orquestradores;
- métodos futuros podem alterar offsets sem redefinir o significado de `cycle_time`.
