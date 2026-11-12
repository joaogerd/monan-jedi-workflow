# Independent domain CLI contract

Status: parser/API contract implemented; new executable apps are not installed yet.
Existing monan-jedi-workflow and monan-jedi-mpas entry points remain unchanged.

The shared parser is `parse_request(app, argv) -> DomainRequest` in
`monan_jedi_workflow.domain_cli`. The request is immutable. Parsing does not
read configuration files, acquire data, import scientific backends or submit jobs.

| Verb | Contract |
|---|---|
| inspect | Read-only view of effective configuration and planned inputs/outputs |
| check | Check configuration, dependencies and inputs without preparing or running |
| prepare | Write runtime configuration, directories and links |
| run | Execute only the prepared operation; no implicit prepare or submission |
| validate | Check resulting products and write validation evidence |
| status | Read-only view of operation, attempt and products |

Grammar:

```text
jedi VERB experiment.yaml --cycle UTC_TIMESTAMP
mpas VERB experiment.yaml --cycle UTC_TIMESTAMP
mpas init VERB experiment.yaml --cycle UTC_TIMESTAMP
obs acquire VERB experiment.yaml --cycle UTC_TIMESTAMP
obs convert VERB experiment.yaml --cycle UTC_TIMESTAMP
diagnostics VERB experiment.yaml --cycle UTC_TIMESTAMP
campaign inspect|check campanha.yaml
campaign export campanha.yaml [--engine simpleworkflow]
```

JEDI means assimilation; root MPAS means forecast. No command executes a whole
cycle. The orchestrator or a user-written shell chains operations. There is no
`obs run` or `campaign run`. Campaign commands do not take --cycle.

All requests accept --json. Only OBS accepts --source. Only campaign export
accepts --engine, defaulting to simpleworkflow. Engine availability is checked by
the future handler, not the parser. Dates require an explicit UTC timestamp with
seconds, using Z or +00:00; spelling is preserved. Invalid syntax exits with code
2. Long option abbreviations are rejected. File existence and domain dependency
checks belong to handlers, so parsing a missing path is valid.

An execution return alone does not make a scientific product consumable:
validation must establish its contract. Handlers, stable JSON result schemas,
error categories, installed apps and backend bindings are follow-on work.

Design: ../superpowers/specs/2026-10-16-platform-domain-apps-design.md
