# Databricks notebook source
# MAGIC %md
# MAGIC # 03 · Análise (qualidade + P1–P5)
# MAGIC Consultas SQL diretamente sobre as tabelas Delta e, em seguida, `scripts/analise.py` (lê as mesmas tabelas).

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Qualidade: completude do índice por atividade
# MAGIC SELECT a.codigo, a.atividade_curta, COUNT(*) AS meses, SUM(f.flag_indice_ausente) AS ausentes,
# MAGIC        ROUND(MIN(f.indice),1) AS minimo, ROUND(MAX(f.indice),1) AS maximo
# MAGIC FROM workspace.industria_juros.fato_producao f JOIN workspace.industria_juros.dim_atividade a USING (sk_atividade)
# MAGIC GROUP BY a.codigo, a.atividade_curta ORDER BY ausentes DESC, a.codigo

# COMMAND ----------

# MAGIC %sql
# MAGIC -- P1: produção dos últimos 12 meses vs média de 2019, por divisão da indústria de transformação
# MAGIC WITH base AS (SELECT sk_atividade, AVG(indice) AS b FROM workspace.industria_juros.fato_producao
# MAGIC               WHERE sk_tempo BETWEEN 201901 AND 201912 GROUP BY sk_atividade),
# MAGIC rec AS (SELECT sk_atividade, AVG(indice) AS r FROM workspace.industria_juros.fato_producao
# MAGIC         WHERE sk_tempo BETWEEN 202508 AND 202607 GROUP BY sk_atividade)
# MAGIC SELECT a.codigo, a.atividade_curta, ROUND((r.r / b.b - 1) * 100, 1) AS var_pct_vs_2019
# MAGIC FROM base b JOIN rec r USING (sk_atividade) JOIN workspace.industria_juros.dim_atividade a USING (sk_atividade)
# MAGIC WHERE a.nivel = 'divisao' ORDER BY var_pct_vs_2019

# COMMAND ----------

# MAGIC %sql
# MAGIC -- P4: volatilidade do crescimento anual (fora de mar/2020–jun/2021, a partir de 2013)
# MAGIC SELECT a.codigo, a.atividade_curta, ROUND(STDDEV(f.var_yoy_pct), 1) AS desvio_yoy_pp
# MAGIC FROM workspace.industria_juros.fato_producao f
# MAGIC JOIN workspace.industria_juros.dim_atividade a USING (sk_atividade)
# MAGIC WHERE f.sk_tempo >= 201301 AND NOT (f.sk_tempo BETWEEN 202003 AND 202106) AND a.nivel = 'divisao'
# MAGIC GROUP BY a.codigo, a.atividade_curta ORDER BY desvio_yoy_pp DESC

# COMMAND ----------

import os, sys, runpy
raiz = os.path.abspath(os.path.join(os.getcwd(), ".."))
resultado = runpy.run_path(os.path.join(raiz, "scripts", "analise.py"), run_name="__main__",
                           init_globals={"spark": spark, "DESTINO": "workspace.industria_juros"})

# COMMAND ----------

import json
print(json.dumps(resultado["R"]["P2"], indent=1, ensure_ascii=False)[:3000])
