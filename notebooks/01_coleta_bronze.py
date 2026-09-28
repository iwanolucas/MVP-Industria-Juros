# Databricks notebook source
# MAGIC %md
# MAGIC # 01 · Coleta (camada bronze)
# MAGIC Baixa PIM-PF (IBGE/SIDRA) e séries macro (BCB/SGS) e grava o JSON bruto em um **Volume** do Unity Catalog.
# MAGIC Pré-requisito: repositório clonado em uma *Git folder* (Workspace > Create > Git folder) para que `../scripts` exista.

# COMMAND ----------

CATALOGO, ESQUEMA = "workspace", "industria_juros"
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGO}.{ESQUEMA}")
spark.sql(f"CREATE VOLUME IF NOT EXISTS {CATALOGO}.{ESQUEMA}.raw")
RAW = f"/Volumes/{CATALOGO}/{ESQUEMA}/raw"

# COMMAND ----------

import os, sys, runpy, shutil, glob
raiz = os.path.abspath(os.path.join(os.getcwd(), ".."))          # raiz do repositório na Git folder
sys.argv = ["coleta.py", RAW]
try:
    runpy.run_path(os.path.join(raiz, "scripts", "coleta.py"), run_name="__main__")
    print("Coleta via API concluída.")
except Exception as e:
    # O Databricks Free Edition não tem saída para a internet (falha de DNS). Nesse caso usa-se o bronze
    # versionado no repositório (data/raw), coletado pelo mesmo script em 28/09/2026 (ver _manifesto_coleta.json).
    print(f"API inacessível neste ambiente ({type(e).__name__}); copiando o bronze versionado do repositório.")
    for arq in glob.glob(os.path.join(raiz, "data", "raw", "*.json")):
        shutil.copy(arq, RAW)

# COMMAND ----------

display(dbutils.fs.ls(RAW))
print(open(f"{RAW}/_manifesto_coleta.json").read()[:1200])
