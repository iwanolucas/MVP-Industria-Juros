"""ETL local (pandas + SQLite) que espelha o notebook Databricks (Spark + Delta).

bronze : JSON bruto em data/raw
silver : tabelas limpas e tipadas
gold   : esquema estrela (dim_tempo, dim_atividade, fato_producao, fato_macro)

Regras de negócio (todas registradas em data/processed/log_etl.json):
 R1  mês em português ("janeiro 2002") -> data (1º dia do mês) e chave sk_tempo = AAAAMM
 R2  código CNAE separado do nome ("3.10 Fabricação ...") -> codigo, nome, nivel
 R3  "-" (sem informação no IBGE) -> NULL; nunca imputado
 R4  valores numéricos convertidos para float; datas do BCB (dd/mm/aaaa) -> 1º dia do mês
 R5  duplicatas por chave natural (mês, atividade) removidas (mantém a 1ª ocorrência)
 R6  var_yoy_pct = índice / índice 12 meses antes - 1 (calculada por atividade)
 R7  selic_real_aa = (1+Selic a.a.)/(1+IPCA 12m) - 1  (juro real ex-post)
 R8  var_cambial_12m_pct = dólar médio / dólar médio 12 meses antes - 1
 R9  fato_macro cobre o intervalo comum às fontes; meses só do BCB (sem PIM-PF) ficam
     fora da análise, mas permanecem na fato_macro com flag_tem_producao = 0
"""
import json
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

MESES = {m: i + 1 for i, m in enumerate(
    "janeiro fevereiro março abril maio junho julho agosto setembro outubro novembro dezembro".split())}
log = {}

# ---------------------------------------------------------------- bronze -> silver: PIM-PF
raw = json.loads((RAW / "pimpf_8888.json").read_text(encoding="utf-8"))
pim = pd.DataFrame(raw[1:])[["D3N", "D4N", "V"]].rename(columns={"D3N": "mes_txt", "D4N": "atividade_txt", "V": "valor_txt"})
log["pim_linhas_brutas"] = len(pim)

m = pim["mes_txt"].str.extract(r"^(\w+)\s+(\d{4})$")
pim["data"] = pd.to_datetime(dict(year=m[1].astype(int), month=m[0].map(MESES), day=1))          # R1
c = pim["atividade_txt"].str.extract(r"^([\d.]+)\s+(.*)$")                                         # R2
pim["codigo"], pim["atividade"] = c[0], c[1]
pim["indice"] = pd.to_numeric(pim["valor_txt"].replace("-", None), errors="coerce")               # R3
log["pim_valores_ausentes_R3"] = int(pim["indice"].isna().sum())
antes = len(pim)
pim = pim.drop_duplicates(["data", "codigo"], keep="first")                                       # R5
log["pim_duplicatas_removidas_R5"] = antes - len(pim)
pim = pim.sort_values(["codigo", "data"]).reset_index(drop=True)
pim["var_yoy_pct"] = pim.groupby("codigo")["indice"].transform(lambda s: (s / s.shift(12) - 1) * 100)  # R6

# ---------------------------------------------------------------- bronze -> silver: BCB
def sgs(nome, col):
    d = pd.DataFrame(json.loads((RAW / f"{nome}.json").read_text(encoding="utf-8")))
    d["data"] = pd.to_datetime(d["data"], format="%d/%m/%Y").dt.to_period("M").dt.to_timestamp()      # R4
    d[col] = pd.to_numeric(d["valor"], errors="coerce")
    d = d.drop_duplicates("data")
    return d[["data", col]].set_index("data")

macro = pd.concat([sgs("sgs_4189_selic_anualizada", "selic_aa"), sgs("sgs_433_ipca_mensal", "ipca_mensal"),
                   sgs("sgs_13522_ipca_12m", "ipca_12m"), sgs("sgs_3698_dolar_medio", "dolar_medio")], axis=1).sort_index()
macro["selic_real_aa"] = ((1 + macro.selic_aa / 100) / (1 + macro.ipca_12m / 100) - 1) * 100           # R7
macro["var_cambial_12m_pct"] = (macro.dolar_medio / macro.dolar_medio.shift(12) - 1) * 100            # R8
macro = macro.reset_index()
macro["flag_tem_producao"] = macro["data"].isin(pim["data"]).astype(int)                            # R9
log["macro_meses"] = len(macro)
log["macro_meses_sem_producao_R9"] = int((macro.flag_tem_producao == 0).sum())

# ---------------------------------------------------------------- silver -> gold (estrela)
def tempo(datas):
    d = pd.DataFrame({"data": sorted(set(datas))})
    d["sk_tempo"] = d.data.dt.year * 100 + d.data.dt.month
    d["ano"], d["mes"] = d.data.dt.year, d.data.dt.month
    d["trimestre"] = d.data.dt.quarter
    d["nome_mes"] = d.data.dt.strftime("%b")
    d["periodo_covid"] = ((d.data >= "2020-03-01") & (d.data <= "2020-12-01")).astype(int)
    d["data"] = d.data.dt.strftime("%Y-%m-%d")
    return d[["sk_tempo", "data", "ano", "mes", "trimestre", "nome_mes", "periodo_covid"]]

dim_tempo = tempo(list(pim.data) + list(macro.data))

dim_atividade = pim[["codigo", "atividade"]].drop_duplicates().reset_index(drop=True)
dim_atividade.insert(0, "sk_atividade", range(1, len(dim_atividade) + 1))
dim_atividade["nivel"] = dim_atividade.codigo.map(lambda x: "geral" if x == "1" else ("secao" if x in ("2", "3") else "divisao"))
dim_atividade["secao_pai"] = dim_atividade.codigo.map(lambda x: None if x in ("1", "2", "3") else "3")
dim_atividade["atividade_curta"] = dim_atividade.atividade.str.replace(
    r"^(Fabricação de|Fabricação|Preparação de)\s+", "", regex=True).str.slice(0, 42)

fato_producao = pim.merge(dim_atividade[["sk_atividade", "codigo"]], on="codigo")
fato_producao["sk_tempo"] = fato_producao.data.dt.year * 100 + fato_producao.data.dt.month
fato_producao["flag_indice_ausente"] = fato_producao.indice.isna().astype(int)
fato_producao = fato_producao[["sk_tempo", "sk_atividade", "indice", "var_yoy_pct", "flag_indice_ausente"]]

fato_macro = macro.copy()
fato_macro.insert(0, "sk_tempo", fato_macro.data.dt.year * 100 + fato_macro.data.dt.month)
fato_macro = fato_macro.drop(columns="data")

# integridade referencial
assert set(fato_producao.sk_tempo) <= set(dim_tempo.sk_tempo)
assert set(fato_macro.sk_tempo) <= set(dim_tempo.sk_tempo)
assert not fato_producao.duplicated(["sk_tempo", "sk_atividade"]).any()
assert not fato_macro.duplicated("sk_tempo").any()

# ---------------------------------------------------------------- carga
db = OUT / "dw_industria.sqlite"
if db.exists():
    db.unlink()
con = sqlite3.connect(db)
tabelas = dict(dim_tempo=dim_tempo, dim_atividade=dim_atividade, fato_producao=fato_producao, fato_macro=fato_macro)
for nome, df in tabelas.items():
    df.to_sql(nome, con, index=False)
    df.to_csv(OUT / f"{nome}.csv", index=False, encoding="utf-8")
    log[f"gold_{nome}_linhas"] = len(df)
con.execute("CREATE INDEX ix_fp ON fato_producao(sk_atividade, sk_tempo)")
con.commit()
con.close()
if "spark" in globals():  # execução no Databricks: persiste as tabelas gold como Delta (Unity Catalog)
    destino = globals().get("DESTINO", "workspace.industria_juros")
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {destino}")
    for nome, df in tabelas.items():
        spark.createDataFrame(df).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(f"{destino}.{nome}")
        log[f"delta_{nome}"] = f"{destino}.{nome}"
(OUT / "log_etl.json").write_text(json.dumps(log, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(log, indent=2, ensure_ascii=False))
