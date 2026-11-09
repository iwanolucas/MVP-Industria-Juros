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

# Por padrão o pipeline parte do bronze versionado no repositório (data/raw, coletado por scripts/coleta.py em
# 28/09/2026, com hash SHA-256 no _manifesto_coleta.json). Isso torna a execução reprodutível: os números do
# relatório não mudam a cada rodada. Para coletar de novo das APIs (requer internet e atualiza os dados), use True.
COLETAR_DAS_APIS = False


def copiar_bronze_versionado():
    for arq in glob.glob(os.path.join(raiz, "data", "raw", "*.json")):
        shutil.copy(arq, RAW)
    print("Bronze versionado copiado para o Volume.")


if COLETAR_DAS_APIS:
    sys.argv = ["coleta.py", RAW]
    try:
        runpy.run_path(os.path.join(raiz, "scripts", "coleta.py"), run_name="__main__")
        print("Coleta via API concluída.")
    except Exception as e:
        # O Databricks Free Edition não tem saída para a internet (falha de DNS em 28/09/2026).
        print(f"API inacessível neste ambiente ({type(e).__name__}).")
        copiar_bronze_versionado()
else:
    copiar_bronze_versionado()

# COMMAND ----------

display(dbutils.fs.ls(RAW))
print(open(f"{RAW}/_manifesto_coleta.json").read()[:1200])
