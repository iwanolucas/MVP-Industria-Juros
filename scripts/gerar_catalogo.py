"""Gera o Catálogo de Dados (catalogo/catalogo_dados.csv e .md) com domínios lidos da própria base."""
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
con = sqlite3.connect(ROOT / "data" / "processed" / "dw_industria.sqlite")

PIM = "IBGE/SIDRA tabela 8888 (PIM-PF), variável 12606, coletada em 28/09/2026"
SGS = "BCB/SGS série {n}, coletada em 28/09/2026"

# tabela, coluna, tipo, descrição, obrigatoriedade, linhagem
META = [
    ("dim_tempo", "sk_tempo", "inteiro (chave)", "Chave do mês no formato AAAAMM.", "Obrigatório", "Gerada no ETL a partir do mês da fonte (R1)."),
    ("dim_tempo", "data", "data", "Primeiro dia do mês.", "Obrigatório", "Mês em português da SIDRA / data dd/mm/aaaa do SGS -> 1º dia do mês (R1, R4)."),
    ("dim_tempo", "ano", "inteiro", "Ano civil.", "Obrigatório", "Derivado de data."),
    ("dim_tempo", "mes", "inteiro", "Mês civil (1–12).", "Obrigatório", "Derivado de data."),
    ("dim_tempo", "trimestre", "inteiro", "Trimestre civil (1–4).", "Obrigatório", "Derivado de data."),
    ("dim_tempo", "nome_mes", "categórico", "Abreviatura inglesa do mês (locale do sistema).", "Obrigatório", "Derivado de data."),
    ("dim_tempo", "periodo_covid", "booleano (0/1)", "1 entre mar/2020 e dez/2020 (choque inicial da pandemia); a análise usa janela mais larga (mar/2020–jun/2021).", "Obrigatório", "Regra fixa do ETL."),
    ("dim_atividade", "sk_atividade", "inteiro (chave)", "Chave substituta da atividade industrial.", "Obrigatório", "Sequência gerada no ETL."),
    ("dim_atividade", "codigo", "categórico (texto)", "Código CNAE 2.0 da seção/divisão (1 = geral; 2 = extrativas; 3 = transformação; 3.10–3.33 = divisões).", "Obrigatório", f"Extraído do rótulo da atividade (R2). {PIM}."),
    ("dim_atividade", "atividade", "texto", "Nome oficial da atividade.", "Obrigatório", f"Extraído do rótulo (R2). {PIM}."),
    ("dim_atividade", "atividade_curta", "texto", "Nome abreviado (sem prefixo 'Fabricação de', máx. 42 caracteres) para gráficos.", "Obrigatório", "Derivado de atividade."),
    ("dim_atividade", "nivel", "categórico", "Nível hierárquico: geral, secao ou divisao.", "Obrigatório", "Derivado do código."),
    ("dim_atividade", "secao_pai", "categórico", "Seção à qual a divisão pertence ('3'). Nulo para geral e seções.", "Admite nulo (nulo = sem pai)", "Derivado do código."),
    ("fato_producao", "sk_tempo", "inteiro (FK)", "Mês da observação.", "Obrigatório", "FK para dim_tempo."),
    ("fato_producao", "sk_atividade", "inteiro (FK)", "Atividade da observação.", "Obrigatório", "FK para dim_atividade."),
    ("fato_producao", "indice", "numérico", "Número-índice de produção física (base 2022 = 100), sem ajuste sazonal.", "Admite nulo (nulo = IBGE não publica a série no mês; nunca imputado)", f"{PIM}. '-' convertido em NULL (R3)."),
    ("fato_producao", "var_yoy_pct", "numérico (%)", "Variação % do índice frente ao mesmo mês do ano anterior.", "Admite nulo (primeiros 12 meses da série e meses após ausências)", "Calculada no ETL (R6)."),
    ("fato_producao", "flag_indice_ausente", "booleano (0/1)", "1 quando o índice é nulo.", "Obrigatório", "Derivado de indice."),
    ("fato_macro", "sk_tempo", "inteiro (FK)", "Mês da observação.", "Obrigatório", "FK para dim_tempo."),
    ("fato_macro", "selic_aa", "numérico (% a.a.)", "Taxa Selic acumulada no mês, anualizada (base 252).", "Obrigatório", SGS.format(n="4189") + "."),
    ("fato_macro", "ipca_mensal", "numérico (% a.m.)", "Variação mensal do IPCA.", "Admite nulo (mês corrente ainda não divulgado)", SGS.format(n="433") + "."),
    ("fato_macro", "ipca_12m", "numérico (%)", "IPCA acumulado em 12 meses.", "Admite nulo (mês corrente ainda não divulgado)", SGS.format(n="13522") + "."),
    ("fato_macro", "dolar_medio", "numérico (R$/US$)", "Taxa de câmbio livre, dólar (venda), média do mês.", "Admite nulo (mês corrente ainda não fechado)", SGS.format(n="3698") + "."),
    ("fato_macro", "selic_real_aa", "numérico (% a.a.)", "Juro real ex-post: (1+Selic)/(1+IPCA 12m) − 1.", "Admite nulo (quando IPCA 12m é nulo)", "Calculada no ETL (R7) a partir de selic_aa e ipca_12m."),
    ("fato_macro", "var_cambial_12m_pct", "numérico (%)", "Variação % do dólar médio frente ao mesmo mês do ano anterior (positivo = real desvalorizado).", "Admite nulo (12 primeiros meses e mês corrente)", "Calculada no ETL (R8)."),
    ("fato_macro", "flag_tem_producao", "booleano (0/1)", "1 quando o mês também existe na PIM-PF (R9).", "Obrigatório", "Derivado no ETL."),
]

linhas = []
for t, c, tipo, desc, obrig, lin in META:
    if "categórico" in tipo:
        vals = pd.read_sql(f"SELECT DISTINCT {c} FROM {t} WHERE {c} IS NOT NULL ORDER BY 1", con)[c].astype(str).tolist()
        dom = ", ".join(vals) if len(vals) <= 8 else f"{len(vals)} categorias (ex.: {', '.join(vals[:4])}, …)"
    elif tipo.startswith(("inteiro", "numérico", "data", "booleano")):
        mn, mx = con.execute(f"SELECT MIN({c}), MAX({c}) FROM {t}").fetchone()
        fmt = lambda v: f"{v:.2f}" if isinstance(v, float) else str(v)
        dom = f"{fmt(mn)} a {fmt(mx)}"
    else:
        n = con.execute(f"SELECT COUNT(DISTINCT {c}) FROM {t}").fetchone()[0]
        dom = f"texto livre ({n} valores distintos)"
    nulos = con.execute(f"SELECT COUNT(*) FROM {t} WHERE {c} IS NULL").fetchone()[0]
    linhas.append(dict(tabela=t, atributo=c, tipo=tipo, descricao=desc, dominio_observado=dom, obrigatoriedade=obrig,
                       nulos_observados=nulos, linhagem=lin))

cat = pd.DataFrame(linhas)
cat.to_csv(ROOT / "catalogo" / "catalogo_dados.csv", index=False, encoding="utf-8")
md = ["# Catálogo de Dados\n", "Domínios lidos diretamente da base (`dw_industria.sqlite`). Regras R1–R9 estão em `scripts/etl.py`.\n"]
for t, g in cat.groupby("tabela", sort=False):
    md.append(f"\n## {t}\n\n| Atributo | Tipo | Descrição | Domínio observado | Obrigatoriedade | Nulos | Linhagem |\n|---|---|---|---|---|---|---|")
    for _, r in g.iterrows():
        md.append(f"| `{r.atributo}` | {r.tipo} | {r.descricao} | {r.dominio_observado} | {r.obrigatoriedade} | {r.nulos_observados} | {r.linhagem} |")
(ROOT / "catalogo" / "catalogo_dados.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print(cat[["tabela", "atributo", "dominio_observado", "nulos_observados"]].to_string())
