"""Coleta (bronze): baixa PIM-PF (IBGE/SIDRA) e séries macro (BCB/SGS) e grava JSON bruto.

Uso: python scripts/coleta.py [pasta_saida]
Gera também data/raw/_manifesto_coleta.json (data, URL, volume, formato).
"""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1] / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

FONTES = {
    # IBGE/SIDRA tabela 8888: PIM-PF, número-índice (2022=100), Brasil, todas as atividades, série completa
    "pimpf_8888": "https://apisidra.ibge.gov.br/values/t/8888/n1/all/v/12606/p/all/c544/all/f/n",
    # BCB/SGS
    "sgs_4189_selic_anualizada": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.4189/dados?formato=json&dataInicial=01/01/2002&dataFinal=30/09/2026",
    "sgs_433_ipca_mensal": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados?formato=json&dataInicial=01/01/2002&dataFinal=30/09/2026",
    "sgs_13522_ipca_12m": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.13522/dados?formato=json&dataInicial=01/01/2002&dataFinal=30/09/2026",
    "sgs_3698_dolar_medio": "https://api.bcb.gov.br/dados/serie/bcdata.sgs.3698/dados?formato=json&dataInicial=01/01/2002&dataFinal=30/09/2026",
}

manifesto = []
for nome, url in FONTES.items():
    for tentativa in range(5):  # a API do BCB às vezes devolve corpo vazio
        r = requests.get(url, timeout=120)
        try:
            r.raise_for_status()
            dados = r.json()
            break
        except ValueError:
            time.sleep(2 * (tentativa + 1))
    else:
        raise RuntimeError(f"Falha ao coletar {nome}")
    arq = OUT / f"{nome}.json"
    arq.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    manifesto.append({
        "arquivo": arq.name,
        "url": url,
        "coletado_em_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "formato_original": "JSON (lista de objetos)",
        "registros": len(dados),
        "bytes": arq.stat().st_size,
        "sha256": hashlib.sha256(arq.read_bytes()).hexdigest(),
    })
    print(f"{nome}: {len(dados)} registros, {arq.stat().st_size/1024:.0f} KB")

(OUT / "_manifesto_coleta.json").write_text(json.dumps(manifesto, indent=2, ensure_ascii=False), encoding="utf-8")
