# Validação científica da beta — referência de setembro de 2025

## Estado em 12/11/2026

Auditoria estática aprovada; execução e equivalência numérica **pendentes**.
A comparação utiliza a captura reconciliada de 14/10/2026 da campanha de
01/09/2025 00Z a 08/09/2025 00Z, associada ao código histórico
`f9b37019ed6b7a27bb9b99c714fb97f5e00b67a3`. A captura geral de 12/10 contém
casos de 2018 e não substitui esta referência.

O manifesto externo `config-sha256.txt` foi conferido contra os 2.419 arquivos
regulares extraídos de `campaign-configs.tar.gz`: nenhuma divergência e nenhum
arquivo adicional. Isso demonstra consistência com a captura, não autenticação
independente da origem. Os templates foram renderizados pelo contexto temporal
da beta e comparados em bytes com os arquivos históricos: 145 arquivos JEDI
(29 × 5) e 56 MPAS (28 × 2), sem diferenças. O resultado está em
`2026-11-12-reference-audit.json`.

Reprodução, com arquivos da captura disponíveis fora do checkout:

```bash
python scripts/audit_scientific_reference.py /caminho/campaign-reference /caminho/config-sha256.txt
```

Esse comando é somente leitura e não executa o modelo. O teste não cobre
resolução de caminhos, manifesto da instalação, submissão PBS, ligação dos
executáveis ou resultados numéricos. Não autoriza declarar a beta validada.

## Contrato científico preservado

- Malha `x1.10242`, aproximadamente 240 km; 55 níveis; mesma matriz B.
- 128 processos MPI, mesma decomposição e mesmo ambiente científico.
- Análises a cada 6 horas; background em T−3 h; janela FGAT de 6 horas.
- Passo do modelo `PT20M`; previsão de 6 h, estados em +3 h e +6 h.
- Mesmos operadores, filtros de observação e minimização da referência.
- Estado completo no centro da análise e trajetória no início da janela são
  entradas distintas; não trocar o arquivo de +3 h pelo de +6 h.

O caso histórico registra 29 análises, 28 previsões entre análises e 29
conversões. Seus diagnósticos publicados registram redução média de J de
28,03445%, RMSE O−B médio por ciclo de 1,199512 K e O−A de 1,094541 K.
Estes números são referências históricas, não resultados recalculados nesta
sessão: os logs e feedbacks completos não estão na captura local.

## Primeiro ensaio na JACI

Usar um diretório novo e preservar o caso original. Registrar commit da beta,
manifesto real da instalação (`share/monan-jedi/install-manifest.json`), hashes
dos executáveis e entradas, stack, bibliotecas, MPI, launcher, recursos PBS e
variáveis de ambiente. Não fabricar um manifesto para satisfazer a verificação.
Uma mudança de binário ou stack exige registrar uma nova condição experimental.

Começar com duas análises (01/09/2025 00Z e 06Z), com a previsão de 00Z entre
elas. Reutilizar inicialmente os IODA históricos e as entradas iniciais para
isolar o comportamento da plataforma. Depois validar a conversão dos mesmos
BUFR separadamente. O suporte à aquisição de arquivos compactados precisa ser
verificado antes de incluir aquisição remota no ensaio.

A sequência pertence ao orquestrador ou a um shell explícito do usuário:
JEDI 00Z → MPAS 00Z → JEDI 06Z. Os aplicativos continuam executando uma etapa e
um instante por chamada. Não introduzir um comando de ciclo completo.

Na adaptação das configurações, alterar apenas destinos e ligações de entrada.
O JEDI 06Z deve consumir a trajetória MPAS 00Z válida às 03Z e o estado completo
válido às 06Z, produzidos pelo candidato. Reutilizar esses dois arquivos do
caso histórico esconderia uma falha no encadeamento. Conferir novamente os
arquivos renderizados antes de submeter. O gerador do piloto agora materializa o experimento principal, a campanha e
um shell PBS explícito. Seguir `run-short-pilot.md`; a verificação da instalação
e dos dados completos continua sendo feita na JACI antes da submissão.

## Critérios de aceite

| Objeto | Verificação | Condição inicial de aceite |
|---|---|---|
| Entradas | Hash, tempo válido, malha, níveis, variáveis e unidades | Mesma referência |
| Configurações | Diff do conteúdo científico e caminhos resolvidos | Só relocação explícita |
| Análises | Estado completo original × candidato | Igualdade dos valores armazenados |
| Previsão | Arquivos +3 h e +6 h original × candidato | Igualdade dos valores armazenados |
| Feedback IODA | Grupos, dimensões, atributos, QC e valores | Igualdade dos valores armazenados |
| Minimização | J não linear inicial e sequência quadrática por iteração | Mesma sequência e contagem |
| O−B/O−A | Mesma amostra pareada e QC | Mesma contagem, bias e RMSE |
| Proveniência | Execuções, ambiente e produtos identificáveis | Registro completo |

Usar comparação exata inicialmente; o comparador ignora apenas `file_id` da
raiz por padrão. Para conferir inclusive esse identificador, usar
`--compare-file-id`. Qualquer tolerância não nula ou outro atributo ignorado
precisa de justificativa científica explícita e registro; nunca ampliar a
margem automaticamente após encontrar diferenças.

```bash
monan-jedi-workflow compare-netcdf ORIGINAL.nc CANDIDATO.nc
python -m monan_jedi_workflow.scientific_feedback FEEDBACK.nc4 --variable airTemperature
```

O comparador agora percorre grupos NetCDF recursivamente, incluindo os grupos
IODA: anteriormente uma diferença só dentro de `hofx1` podia passar despercebida.
O diagnóstico pareado lê `ObsValue`, `hofx0`, `hofx1`, exclui máscaras e valores
não finitos e aplica a interseção dos `EffectiveQC0/1` disponíveis iguais a zero;
usa `EffectiveQC` quando não há grupos numerados. Ausência de QC, unidades
incompatíveis ou amostra vazia provoca erro. Registrar quais grupos foram usados
e comparar também o inventário de grupos entre referência e candidato.

O relatório histórico agrega a média aritmética dos RMSEs por ciclo; não
comparar essa média com um RMSE agrupado de todas as observações. Para J,
extrair `CostFunction: Nonlinear J` e `Quadratic cost function: J(i)` sem somar
as linhas de componentes Jb/JoJc nem misturar tentativas de execução.
O ajuste às observações assimiladas não demonstra habilidade de previsão
independente. Monotonicidade e redução de RMSE são verificações auxiliares;
a repetição dos números históricos é o primeiro controle de equivalência.

Após aprovar o ensaio curto, repetir a campanha de sete dias. Uma execução de
15 km ou 30 dias constitui uma etapa posterior, não substitui esse controle.

## Limitação operacional atual

Este ambiente não possui os dados científicos completos, instalação MONAN-JEDI
ou acesso SSH configurado à JACI. Nenhum job científico foi submetido e nenhum
produto numérico da beta foi declarado equivalente. A próxima evidência
necessária é a execução isolada na JACI e seus arquivos, logs e proveniência.
