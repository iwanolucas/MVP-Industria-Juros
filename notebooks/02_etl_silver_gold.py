# Databricks notebook source
# MAGIC %md
# MAGIC # 02 · ETL (silver → gold, esquema estrela em Delta)
# MAGIC Executa `scripts/etl.py` (regras R1–R9 documentadas no cabeçalho) sobre o JSON do Volume e grava
# MAGIC `dim_tempo`, `dim_atividade`, `fato_producao` e `fato_macro` como **tabelas Delta** em `workspace.industria_juros`.

# COMMAND ----------

import os, sys, runpy
DESTINO = "workspace.industria_juros"
RAW = "/Volumes/workspace/industria_juros/raw"
raiz = os.path.abspath(os.path.join(os.getcwd(), ".."))
sys.argv = ["etl.py", RAW]
runpy.run_path(os.path.join(raiz, "scripts", "etl.py"), run_name="__main__",
               init_globals={"spark": spark, "DESTINO": DESTINO})

# COMMAND ----------

# MAGIC %sql
# MAGIC SELECT 'dim_tempo' AS tabela, COUNT(*) AS linhas FROM workspace.industria_juros.dim_tempo
# MAGIC UNION ALL SELECT 'dim_atividade', COUNT(*) FROM workspace.industria_juros.dim_atividade
# MAGIC UNION ALL SELECT 'fato_producao', COUNT(*) FROM workspace.industria_juros.fato_producao
# MAGIC UNION ALL SELECT 'fato_macro', COUNT(*) FROM workspace.industria_juros.fato_macro

# COMMAND ----------

# MAGIC %sql
# MAGIC -- prova de persistência: histórico Delta da tabela fato
# MAGIC DESCRIBE HISTORY workspace.industria_juros.fato_producao
