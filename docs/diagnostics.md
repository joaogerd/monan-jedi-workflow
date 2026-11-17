# Diagnóstico de erros — MONAN-JEDI

Quando uma operação falhar, **não é necessário interpretar arquivos de log ou
comandos do PBS manualmente**. A partir do diretório do experimento, execute:

```bash
monan-jedi-workflow diagnose
```

Também é possível informar o diretório explicitamente:

```bash
monan-jedi-workflow diagnose /p/projetos/<grupo>/<usuario>/work/<experimento>
```

O comando é somente leitura e não remove resultados, altera configurações,
submete jobs ou tenta executar novamente o experimento.

O relatório mostra:

- A operação que falhou e seu estado;
- O código de saída PBS quando o histórico estiver disponível;
- O erro principal encontrado nos logs (mensagens idênticas de MPI são agrupadas);
- Os produtos e as mensagens de conclusão não encontrados;
- Uma explicação compreensível da causa provável e uma orientação de correção.

Quando não há evidências suficientes, o relatório diz que **não foi possível
determinar a causa** e aponta os arquivos a examinar. Não classifica um erro
como resolvido apenas porque o job saiu da fila.

## Exemplo: biblioteca compartilhada ausente

A apresentação padrão prioriza apenas o que interessa para resolver:

```text
MONAN-JEDI  |  Diagnóstico da execução
--------------------------------------------------------------
[FALHA] MPAS INIT  |  ciclo 20250831T180000Z

CAUSA IDENTIFICADA
  O executável não iniciou: biblioteca libfabric.so.1
  indisponível no nó de computação.
  Job PBS: 826106.pbs-ha  |  código de saída: 127

EVIDÊNCIA PRINCIPAL
  ./mpas_init_atmosphere: error while loading shared libraries:
  libfabric.so.1: cannot open shared object file
  (128 ocorrências da mesma mensagem MPI)

AÇÃO RECOMENDADA
  Conferir os módulos MPI/Cray e o LD_LIBRARY_PATH do job PBS.

CONSEQUÊNCIA
  1 arquivo científico esperado não produzido.

Detalhes adicionais: monan-jedi-workflow diagnose --verbose
--------------------------------------------------------------
```

Para dados extensos (outros jobs, caminhos completos, recursos PBS e
relatórios de validação), execute:

```bash
monan-jedi-workflow diagnose --verbose
```

Se a falha envolver libfabric na JACI, o caminho declarado em
`MONAN_LIBFABRIC_ROOT` deve apontar para uma instalação compatível
disponível nos compute nodes. O bootstrap gerado para os scripts científicos
adiciona essa instalação ao `LD_LIBRARY_PATH`, depois de conferir a existência
de `libfabric.so.1`. **O Conda do controlador continua no login.**

A ferramenta não sugere copiar bibliotecas nem criar links simbólicos
artificiais.

## Integração e suporte

Os aplicativos imprimem o comando de diagnóstico quando a etapa `run` ou
`validate` falha. Para enviar um relatório à equipe técnica, use:

```bash
monan-jedi-workflow diagnose --json
```

O relatório JSON permite reproduzir a análise, mas pode conter diretórios
internos, identificadores de jobs e trechos de logs: revise-o antes de
compartilhar fora da sua organização.

Se o serviço PBS estiver indisponível, o diagnóstico ainda funciona usando
apenas os arquivos locais:

```bash
monan-jedi-workflow diagnose --no-pbs
```

**Importante:** ainda não há correção ou retomada automática. Isso é
intencional: uma submissão duplicada pode sobrescrever saídas e desperdiçar
recursos computacionais. Após resolver a causa, confira o estado anterior
antes de reiniciar ou criar uma nova execução.
