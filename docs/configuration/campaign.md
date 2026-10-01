# Configuração da campanha

A campanha responde somente: **quando começa, por quanto tempo roda, qual
configuração científica usa e onde escrever o caso**.

Use `examples/campaigns/template.yaml` como ponto de partida.

```yaml
campaign:
  name: meu-experimento
  start: 2025-01-01T00:00:00Z
  duration: P3D
  cycle_interval_hours: 6
  destination: cases/meu-experimento

profile: profiles/meu-experimento.yaml

forecast:
  run_on_last_cycle: true

execution:
  swf_command: swf
```

## Chaves

| chave | obrigatório | significado |
| --- | --- | --- |
| `campaign.name` | sim | identificador humano do experimento |
| `campaign.start` | sim | horário da primeira análise, ISO-8601 UTC |
| `campaign.duration` | sim | duração; use `P3D`, `P7D`, `P30D` ou `P365D` |
| `campaign.cycle_interval_hours` | não | intervalo entre análises; default atual 6 h |
| `campaign.destination` | sim | diretório novo onde o caso será materializado |
| `profile` | sim | arquivo que aponta para os quatro componentes científicos |
| `forecast.run_on_last_cycle` | não | executa forecast também após a última análise |
| `execution.swf_command` | não | comando do simpleWorkflow; default `swf` |

O ano, a data e a duração acima são **exemplo**, não defaults científicos.
