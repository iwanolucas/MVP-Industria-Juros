"""Regras de domínio esperado (catálogo) e nomes curtos das atividades (apresentação).

Usado por gerar_catalogo.py (coluna "Domínio esperado") e por analise.py (teste de
conformidade atributo a atributo). Os limites são declarados a priori, pelo significado
do dado, e não lidos da base: a análise de qualidade confere se a base os respeita.
"""

# Nomes curtos e legíveis para tabelas e gráficos (o nome oficial do IBGE fica em dim_atividade.atividade).
NOMES_CURTOS = {
    "1": "Indústria geral",
    "2": "Indústrias extrativas",
    "3": "Indústrias de transformação",
    "3.10": "Alimentos",
    "3.11": "Bebidas",
    "3.12": "Fumo",
    "3.13": "Têxteis",
    "3.14": "Vestuário e acessórios",
    "3.15": "Couro, artigos de viagem e calçados",
    "3.16": "Madeira",
    "3.17": "Celulose e papel",
    "3.18": "Impressão e reprodução de gravações",
    "3.19": "Derivados de petróleo e biocombustíveis",
    "3.20": "Químicos",
    "3.21": "Farmoquímicos e farmacêuticos",
    "3.22": "Borracha e plástico",
    "3.23": "Minerais não metálicos",
    "3.24": "Metalurgia",
    "3.25": "Produtos de metal",
    "3.26": "Informática, eletrônicos e ópticos",
    "3.27": "Máquinas e materiais elétricos",
    "3.28": "Máquinas e equipamentos",
    "3.29": "Veículos automotores",
    "3.30": "Outros equipamentos de transporte",
    "3.31": "Móveis",
    "3.32": "Produtos diversos",
    "3.33": "Manutenção e reparação de máquinas",
}

MESES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CODIGOS = list(NOMES_CURTOS)

# (tabela, atributo) -> ("faixa", mín, máx, justificativa) ou ("lista", valores, justificativa)
# None em mín/máx = sem limite daquele lado.
DOMINIOS = {
    ("dim_tempo", "sk_tempo"): ("faixa", 200201, 202612, "AAAAMM entre jan/2002 (início da coleta) e dez/2026."),
    ("dim_tempo", "data"): ("faixa", "2002-01-01", "2026-12-01", "1º dia do mês, no período coletado."),
    ("dim_tempo", "ano"): ("faixa", 2002, 2026, "Período coletado."),
    ("dim_tempo", "mes"): ("faixa", 1, 12, "Mês civil."),
    ("dim_tempo", "trimestre"): ("faixa", 1, 4, "Trimestre civil."),
    ("dim_tempo", "nome_mes"): ("lista", MESES, "Abreviatura do mês gerada pelo locale do ambiente (inglês)."),
    ("dim_tempo", "periodo_covid"): ("lista", [0, 1], "Booleano."),
    ("dim_atividade", "sk_atividade"): ("faixa", 1, 27, "Uma chave por atividade da tabela 8888."),
    ("dim_atividade", "codigo"): ("lista", CODIGOS, "Códigos da tabela 8888 (1, 2, 3 e divisões 3.10 a 3.33)."),
    ("dim_atividade", "atividade"): ("texto", None, "Texto livre, um por código."),
    ("dim_atividade", "atividade_curta"): ("texto", None, "Texto livre, um por código."),
    ("dim_atividade", "nivel"): ("lista", ["geral", "secao", "divisao"], "Hierarquia da CNAE."),
    ("dim_atividade", "secao_pai"): ("lista", ["3"], "Só as divisões têm pai (seção 3)."),
    ("fato_producao", "sk_tempo"): ("faixa", 200201, 202612, "Deve existir em dim_tempo."),
    ("fato_producao", "sk_atividade"): ("faixa", 1, 27, "Deve existir em dim_atividade."),
    ("fato_producao", "indice"): ("faixa", 0.01, 500, "Número-índice (2022 = 100): estritamente positivo; acima de 5x a base seria implausível."),
    ("fato_producao", "var_yoy_pct"): ("faixa", -100, None, "Variação percentual: não pode ser menor que −100%. Sem teto (rebotes sobre base deprimida)."),
    ("fato_producao", "flag_indice_ausente"): ("lista", [0, 1], "Booleano."),
    ("fato_macro", "sk_tempo"): ("faixa", 200201, 202612, "Deve existir em dim_tempo."),
    ("fato_macro", "selic_aa"): ("faixa", 0, 50, "Selic anualizada: não negativa; 50% a.a. cobre o pior período desde o Real."),
    ("fato_macro", "ipca_mensal"): ("faixa", -2, 5, "Inflação mensal pós-Real nunca saiu de −2% a +5% a.m."),
    ("fato_macro", "ipca_12m"): ("faixa", -5, 30, "Inflação em 12 meses no regime de metas."),
    ("fato_macro", "dolar_medio"): ("faixa", 1, 10, "R$/US$ desde 2002."),
    ("fato_macro", "selic_real_aa"): ("faixa", -15, 30, "Juro real ex-post plausível."),
    ("fato_macro", "var_cambial_12m_pct"): ("faixa", -100, None, "Variação percentual: piso de −100%."),
    ("fato_macro", "flag_tem_producao"): ("lista", [0, 1], "Booleano."),
}


# Tabela de consumo gerada pela análise (fora do teste de qualidade da carga, que roda antes dela existir).
DOMINIOS_CONSUMO = {
    ("mapa_risco", "sk_atividade"): ("faixa", 4, 27, "Só divisões da transformação (chaves 4 a 27)."),
    ("mapa_risco", "codigo"): ("lista", [c for c in CODIGOS if c.startswith("3.")], "Divisões 3.10 a 3.33."),
    ("mapa_risco", "atividade"): ("texto", None, "Nome curto da divisão."),
    ("mapa_risco", "folga_pp"): ("faixa", -100, 100, "% abaixo da média de 2019 (negativo = acima)."),
    ("mapa_risco", "instabilidade_pp"): ("faixa", 0, None, "Desvio-padrão: não negativo."),
    ("mapa_risco", "expos_juro_pp"): ("faixa", -50, 50, "Diferença de crescimento anual entre ciclos, em p.p."),
    ("mapa_risco", "expos_cambio_pp"): ("faixa", -5, 5, "Coeficiente por 1% de desvalorização, em p.p."),
    ("mapa_risco", "indice_risco"): ("faixa", -5, 5, "Média de escores padronizados."),
    ("mapa_risco", "ranking"): ("faixa", 1, 24, "Posição no índice (1 = maior risco)."),
    ("mapa_risco", "faixa"): ("lista", ["alto", "médio", "baixo"], "Terços do ranking."),
}


def texto_dominio(regra):
    tipo = regra[0]
    if tipo == "faixa":
        mn, mx = regra[1], regra[2]
        fmt = lambda v: str(v).replace(".", ",")
        if mx is None:
            return f"≥ {fmt(mn)}"
        if mn is None:
            return f"≤ {fmt(mx)}"
        return f"{fmt(mn)} a {fmt(mx)}"
    if tipo == "lista":
        vals = [str(v) for v in regra[1]]
        return ", ".join(vals) if len(vals) <= 6 else f"{len(vals)} valores ({', '.join(vals[:3])}, …)"
    return "texto livre"


def fora_do_dominio(serie, regra):
    """Quantidade de valores não nulos fora do domínio esperado."""
    s = serie.dropna()
    tipo = regra[0]
    if tipo == "faixa":
        mn, mx = regra[1], regra[2]
        if isinstance(mn, str) or isinstance(mx, str):
            import pandas as pd
            s = pd.to_datetime(s)
            mn = pd.Timestamp(mn) if mn is not None else None
            mx = pd.Timestamp(mx) if mx is not None else None
        import pandas as pd
        ruim = pd.Series(False, index=s.index)
        if mn is not None:
            ruim |= s < mn
        if mx is not None:
            ruim |= s > mx
        return int(ruim.sum())
    if tipo == "lista":
        validos = {str(v) for v in regra[1]}
        return int((~s.astype(str).isin(validos)).sum())
    return 0
