# Comparar dois arquivos NetCDF

Use este comando para verificar se duas saidas MONAN/MPAS-JEDI possuem a mesma estrutura, metadados cientificos e valores armazenados:

```bash
monan-jedi-workflow compare-netcdf referencia.nc candidato.nc
```

A comparacao verifica:

- dimensoes e seus tamanhos;
- inventario de variaveis;
- tipo e dimensoes de cada variavel;
- atributos globais e atributos das variaveis;
- valores armazenados em todas as variaveis.

Os dados sao lidos em blocos, portanto o comando pode ser usado com arquivos MPAS grandes sem carregar o arquivo inteiro na memoria.

## `file_id`

Por padrao o atributo global `file_id` e ignorado. O MPAS pode gerar um identificador diferente a cada escrita mesmo quando todos os campos cientificos sao identicos.

Para comparar tambem o `file_id`:

```bash
monan-jedi-workflow compare-netcdf ref.nc novo.nc --compare-file-id
```

Para ignorar outro atributo global:

```bash
monan-jedi-workflow compare-netcdf ref.nc novo.nc \
  --ignore-global-attr history
```

A opcao pode ser repetida.

## Comparacao exata e tolerancia numerica

O padrao e comparacao exata dos valores armazenados:

```bash
monan-jedi-workflow compare-netcdf ref.nc novo.nc
```

Quando a reproducibilidade esperada e numerica, mas nao bit a bit, use tolerancias explicitamente:

```bash
monan-jedi-workflow compare-netcdf ref.nc novo.nc \
  --rtol 1e-12 \
  --atol 1e-14
```

Nao use tolerancias sem registrar por que elas sao cientificamente aceitaveis para o teste.

## Saida e codigo de retorno

Arquivos equivalentes produzem uma mensagem como:

```text
Variables compared : 13
Variables equivalent: 13
Ignored global attrs: file_id
Numeric tolerance   : rtol=0, atol=0

[OK] NetCDF scientific contents are equivalent.
```

O codigo de retorno e:

- `0`: arquivos equivalentes segundo as regras escolhidas;
- `1`: diferencas encontradas.

Isso permite usar o comando em scripts, testes de regressao e CI:

```bash
if monan-jedi-workflow compare-netcdf baseline.nc result.nc; then
  echo "reproducao confirmada"
else
  echo "resultado diferente do baseline"
fi
```

Quando uma variavel numerica difere, o relatorio inclui o numero de elementos diferentes e estatisticas como `max_abs` e `mean_abs`.
