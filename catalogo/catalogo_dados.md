# Catálogo de Dados

Domínios lidos diretamente da base (`dw_industria.sqlite`). Regras R1–R9 estão em `scripts/etl.py`.


## dim_tempo

| Atributo | Tipo | Descrição | Domínio observado | Obrigatoriedade | Nulos | Linhagem |
|---|---|---|---|---|---|---|
| `sk_tempo` | inteiro (chave) | Chave do mês no formato AAAAMM. | 200201 a 202609 | Obrigatório | 0 | Gerada no ETL a partir do mês da fonte (R1). |
| `data` | data | Primeiro dia do mês. | 2002-01-01 a 2026-09-01 | Obrigatório | 0 | Mês em português da SIDRA / data dd/mm/aaaa do SGS -> 1º dia do mês (R1, R4). |
| `ano` | inteiro | Ano civil. | 2002 a 2026 | Obrigatório | 0 | Derivado de data. |
| `mes` | inteiro | Mês civil (1–12). | 1 a 12 | Obrigatório | 0 | Derivado de data. |
| `trimestre` | inteiro | Trimestre civil (1–4). | 1 a 4 | Obrigatório | 0 | Derivado de data. |
| `nome_mes` | categórico | Abreviatura inglesa do mês (locale do sistema). | 12 categorias (ex.: Apr, Aug, Dec, Feb, …) | Obrigatório | 0 | Derivado de data. |
| `periodo_covid` | booleano (0/1) | 1 entre mar/2020 e dez/2020 (choque inicial da pandemia); a análise usa janela mais larga (mar/2020–jun/2021). | 0 a 1 | Obrigatório | 0 | Regra fixa do ETL. |

## dim_atividade

| Atributo | Tipo | Descrição | Domínio observado | Obrigatoriedade | Nulos | Linhagem |
|---|---|---|---|---|---|---|
| `sk_atividade` | inteiro (chave) | Chave substituta da atividade industrial. | 1 a 27 | Obrigatório | 0 | Sequência gerada no ETL. |
| `codigo` | categórico (texto) | Código CNAE 2.0 da seção/divisão (1 = geral; 2 = extrativas; 3 = transformação; 3.10–3.33 = divisões). | 27 categorias (ex.: 1, 2, 3, 3.10, …) | Obrigatório | 0 | Extraído do rótulo da atividade (R2). IBGE/SIDRA tabela 8888 (PIM-PF), variável 12606, coletada em 28/09/2026. |
| `atividade` | texto | Nome oficial da atividade. | texto livre (27 valores distintos) | Obrigatório | 0 | Extraído do rótulo (R2). IBGE/SIDRA tabela 8888 (PIM-PF), variável 12606, coletada em 28/09/2026. |
| `atividade_curta` | texto | Nome abreviado (sem prefixo 'Fabricação de', máx. 42 caracteres) para gráficos. | texto livre (27 valores distintos) | Obrigatório | 0 | Derivado de atividade. |
| `nivel` | categórico | Nível hierárquico: geral, secao ou divisao. | divisao, geral, secao | Obrigatório | 0 | Derivado do código. |
| `secao_pai` | categórico | Seção à qual a divisão pertence ('3'). Nulo para geral e seções. | 3 | Admite nulo (nulo = sem pai) | 3 | Derivado do código. |

## fato_producao

| Atributo | Tipo | Descrição | Domínio observado | Obrigatoriedade | Nulos | Linhagem |
|---|---|---|---|---|---|---|
| `sk_tempo` | inteiro (FK) | Mês da observação. | 200201 a 202607 | Obrigatório | 0 | FK para dim_tempo. |
| `sk_atividade` | inteiro (FK) | Atividade da observação. | 1 a 27 | Obrigatório | 0 | FK para dim_atividade. |
| `indice` | numérico | Número-índice de produção física (base 2022 = 100), sem ajuste sazonal. | 9.39 a 316.93 | Admite nulo (nulo = IBGE não publica a série no mês; nunca imputado) | 240 | IBGE/SIDRA tabela 8888 (PIM-PF), variável 12606, coletada em 28/09/2026. '-' convertido em NULL (R3). |
| `var_yoy_pct` | numérico (%) | Variação % do índice frente ao mesmo mês do ano anterior. | -92.11 a 938.77 | Admite nulo (primeiros 12 meses da série e meses após ausências) | 564 | Calculada no ETL (R6). |
| `flag_indice_ausente` | booleano (0/1) | 1 quando o índice é nulo. | 0 a 1 | Obrigatório | 0 | Derivado de indice. |

## fato_macro

| Atributo | Tipo | Descrição | Domínio observado | Obrigatoriedade | Nulos | Linhagem |
|---|---|---|---|---|---|---|
| `sk_tempo` | inteiro (FK) | Mês da observação. | 200201 a 202609 | Obrigatório | 0 | FK para dim_tempo. |
| `selic_aa` | numérico (% a.a.) | Taxa Selic acumulada no mês, anualizada (base 252). | 1.90 a 26.32 | Obrigatório | 0 | BCB/SGS série 4189, coletada em 28/09/2026. |
| `ipca_mensal` | numérico (% a.m.) | Variação mensal do IPCA. | -0.68 a 3.02 | Admite nulo (mês corrente ainda não divulgado) | 1 | BCB/SGS série 433, coletada em 28/09/2026. |
| `ipca_12m` | numérico (%) | IPCA acumulado em 12 meses. | 1.88 a 17.24 | Admite nulo (mês corrente ainda não divulgado) | 1 | BCB/SGS série 13522, coletada em 28/09/2026. |
| `dolar_medio` | numérico (R$/US$) | Taxa de câmbio livre, dólar (venda), média do mês. | 1.56 a 6.10 | Admite nulo (mês corrente ainda não fechado) | 1 | BCB/SGS série 3698, coletada em 28/09/2026. |
| `selic_real_aa` | numérico (% a.a.) | Juro real ex-post: (1+Selic)/(1+IPCA 12m) − 1. | -4.44 a 12.95 | Admite nulo (quando IPCA 12m é nulo) | 1 | Calculada no ETL (R7) a partir de selic_aa e ipca_12m. |
| `var_cambial_12m_pct` | numérico (%) | Variação % do dólar médio frente ao mesmo mês do ano anterior (positivo = real desvalorizado). | -26.90 a 67.45 | Admite nulo (12 primeiros meses e mês corrente) | 13 | Calculada no ETL (R8). |
| `flag_tem_producao` | booleano (0/1) | 1 quando o mês também existe na PIM-PF (R9). | 0 a 1 | Obrigatório | 0 | Derivado no ETL. |
