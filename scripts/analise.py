"""Análise (qualidade de dados + perguntas P1–P5). Lê o DW SQLite gerado por etl.py.

Saídas: data/processed/resultados.json, data/processed/tab_*.csv, evidencias/*.png,
        catalogo/diagrama_estrela.png
"""
import json
import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC, EVID = ROOT / "data" / "processed", ROOT / "evidencias"
EVID.mkdir(exist_ok=True)
PROC.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(42)
if "spark" in globals():   # Databricks: lê as tabelas Delta e espelha em SQLite em memória (mesmo SQL nos dois ambientes)
    destino = globals().get("DESTINO", "workspace.industria_juros")
    con = sqlite3.connect(":memory:")
    for _t in ["dim_tempo", "dim_atividade", "fato_producao", "fato_macro"]:
        spark.table(f"{destino}.{_t}").toPandas().to_sql(_t, con, index=False)
else:
    con = sqlite3.connect(PROC / "dw_industria.sqlite")
R = {}  # resultados

plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150, "axes.titleweight": "bold"})
AZUL, LARANJA, CINZA, VERDE, VERM = "#1f4e79", "#d9822b", "#8a8a8a", "#2e8b57", "#c0392b"

# ------------------------------------------------------------------ consulta SQL principal
SQL = """
SELECT t.data, t.ano, t.periodo_covid, a.codigo, a.atividade_curta AS atividade, a.nivel,
       f.indice, f.var_yoy_pct, m.selic_aa, m.ipca_mensal, m.ipca_12m, m.selic_real_aa,
       m.dolar_medio, m.var_cambial_12m_pct
FROM fato_producao f
JOIN dim_tempo t USING (sk_tempo)
JOIN dim_atividade a USING (sk_atividade)
LEFT JOIN fato_macro m USING (sk_tempo)
ORDER BY a.codigo, t.data"""
df = pd.read_sql(SQL, con, parse_dates=["data"])
macro = pd.read_sql("SELECT m.*, t.data FROM fato_macro m JOIN dim_tempo t USING(sk_tempo)", con,
                    parse_dates=["data"]).set_index("data")

# ================================================================== QUALIDADE
n_meses = df.data.nunique()
aus_df = df[df.indice.isna()]
R["q_indice_ausentes_total"] = int(len(aus_df))
R["q_indice_ausentes_por_atividade"] = {c: int(v) for c, v in aus_df.groupby("codigo").size().items()}
R["q_indice_ausentes_intervalo"] = [str(aus_df.data.min().date()), str(aus_df.data.max().date())]
R["q_indice_nao_positivos"] = int((df.indice <= 0).sum())
R["q_meses_pim"] = int(n_meses)
R["q_periodo_pim"] = [str(df.data.min().date()), str(df.data.max().date())]
R["q_indice_min_max_global"] = [float(df.indice.min()), float(df.indice.max())]

# unicidade / completude temporal
esperado = pd.date_range(df.data.min(), df.data.max(), freq="MS")
R["q_lacunas_temporais"] = int(sum(len(esperado.difference(g.data)) for _, g in df.groupby("codigo")))
R["q_duplicatas_chave"] = int(df.duplicated(["data", "codigo"]).sum())


# conformidade / acurácia: outliers do yoy por atividade (|z robusto| > 5)
def z_rob(s):
    med, mad = s.median(), (s - s.median()).abs().median() * 1.4826
    return (s - med) / mad


d2 = df.dropna(subset=["var_yoy_pct"]).copy()
d2["z"] = d2.groupby("codigo").var_yoy_pct.transform(z_rob)
out = d2[d2.z.abs() > 5]
em_pand = (out.data >= "2020-03-01") & (out.data <= "2021-06-01")
R["q_outliers_yoy_total"] = int(len(out))
R["q_outliers_yoy_em_pandemia_2020_21"] = int(em_pand.sum())
R["q_outliers_yoy_fora_pandemia"] = int((~em_pand).sum())
R["q_outliers_yoy_top"] = (out.assign(d=out.data.dt.strftime("%Y-%m"))
                           .sort_values("z", key=abs, ascending=False)
                           .head(6)[["d", "codigo", "var_yoy_pct"]].round(1).to_dict("records"))

# consistência: (a) yoy recalculado; (b) IPCA 12m oficial vs composição do mensal; (c) agregados
chk = df[df.codigo == "1"].set_index("data")
R["q_consist_yoy_max_diff"] = float((chk.indice / chk.indice.shift(12) * 100 - 100 - chk.var_yoy_pct).abs().max())
comp = ((1 + macro.ipca_mensal / 100).rolling(12).apply(np.prod, raw=True) - 1) * 100
dif = (comp - macro.ipca_12m).abs().dropna()
R["q_ipca12m_vs_composto_max_diff_pp"] = float(dif.max())
R["q_ipca12m_vs_composto_medio_pp"] = float(dif.mean())
sec = df[df.codigo.isin(["2", "3"])].pivot(index="data", columns="codigo", values="indice")
geral = df[df.codigo == "1"].set_index("data").indice
dentro = ((geral >= sec.min(axis=1) - 0.5) & (geral <= sec.max(axis=1) + 0.5)).mean()
R["q_geral_entre_secoes_pct"] = float(100 * dentro)

# domínio macro
R["q_macro_dominios"] = {c: [float(macro[c].min()), float(macro[c].max())] for c in
                         ["selic_aa", "ipca_mensal", "ipca_12m", "dolar_medio", "selic_real_aa"]}
R["q_macro_nulos"] = {c: int(macro[c].isna().sum()) for c in ["selic_aa", "ipca_mensal", "ipca_12m", "dolar_medio"]}
R["q_macro_ultimo_mes"] = str(macro.index.max().date())
R["q_defasagem_pim_vs_macro_meses"] = int((macro.index.max().year - df.data.max().year) * 12
                                          + macro.index.max().month - df.data.max().month)

# ================================================================== amostra de análise
AMOSTRA_INI = pd.Timestamp("2013-01-01")   # início comum a todas as 27 séries com yoy calculável
LAGS = list(range(0, 13))


def fora_covid(idx):
    """True para meses fora de mar/2020–jun/2021 (yoy distorcido por choque e rebote)."""
    return ~((idx >= "2020-03-01") & (idx <= "2021-06-01"))


mac = macro[["selic_real_aa", "var_cambial_12m_pct"]].copy()
for k in LAGS:
    mac[f"sr_l{k}"] = mac.selic_real_aa.shift(k)
YOY = df.pivot(index="data", columns="codigo", values="var_yoy_pct")
nomes = df.drop_duplicates("codigo").set_index("codigo").atividade
R["amostra_meses"] = int(((YOY.index >= AMOSTRA_INI) & fora_covid(YOY.index)).sum())


def amostra(cod, cols):
    d = pd.concat([YOY[cod].rename("y")] + [mac[c] for c in cols], axis=1).dropna()
    return d[(d.index >= AMOSTRA_INI) & fora_covid(d.index)]


# ================================================================== P1: recuperação pré-pandemia
base = df[df.ano == 2019].groupby("codigo").indice.mean()
rec = df[df.data > df.data.max() - pd.DateOffset(months=12)].groupby("codigo").indice.mean()
fundo = df[(df.data >= "2020-03-01") & (df.data <= "2020-07-01")].groupby("codigo").indice.min()
p1 = pd.DataFrame({"atividade": nomes, "base_2019": base, "ult12m": rec, "fundo_2020": fundo})
p1["razao_ult12m_2019"] = p1.ult12m / p1.base_2019
p1["queda_maxima_2020_pct"] = (p1.fundo_2020 / p1.base_2019 - 1) * 100


def meses_recup(cod):
    s = df[(df.codigo == cod) & (df.data >= "2020-03-01")].set_index("data").indice
    ok = (s >= base[cod]).rolling(3).sum().shift(-2) == 3   # 3 meses seguidos acima da média de 2019
    if not ok.any():
        return np.nan
    t = ok[ok].index[0]
    return (t.year - 2020) * 12 + t.month - 3


p1["meses_ate_recuperar"] = [meses_recup(c) for c in p1.index]
p1 = p1.sort_values("razao_ult12m_2019")
p1.round(3).to_csv(PROC / "tab_P1_recuperacao.csv", encoding="utf-8")
sub = p1[p1.index.str.startswith("3.")]
R["P1"] = dict(
    n_divisoes=int(len(sub)), abaixo=int((sub.razao_ult12m_2019 < 1).sum()), acima=int((sub.razao_ult12m_2019 >= 1).sum()),
    geral_razao=float(p1.loc["1", "razao_ult12m_2019"]), extrativas=float(p1.loc["2", "razao_ult12m_2019"]),
    transformacao=float(p1.loc["3", "razao_ult12m_2019"]),
    piores=[(c, p1.loc[c, "atividade"], round(float(p1.loc[c, "razao_ult12m_2019"]), 3)) for c in sub.index[:5]],
    melhores=[(c, p1.loc[c, "atividade"], round(float(p1.loc[c, "razao_ult12m_2019"]), 3)) for c in sub.index[::-1][:5]],
    geral_queda_2020=float(p1.loc["1", "queda_maxima_2020_pct"]),
    geral_meses=None if np.isnan(p1.loc["1", "meses_ate_recuperar"]) else float(p1.loc["1", "meses_ate_recuperar"]),
    transf_meses=None if np.isnan(p1.loc["3", "meses_ate_recuperar"]) else float(p1.loc["3", "meses_ate_recuperar"]),
    nunca_recuperou=[c for c in sub.index if np.isnan(sub.loc[c, "meses_ate_recuperar"])],
    mediana_meses=float(sub.meses_ate_recuperar.median()),
)


# ================================================================== P2: sensibilidade ao juro real por defasagem
# matriz T x 27 do yoy, máscara da amostra e correlação vetorizada por defasagem
Ymat = YOY.values
Mamostra = ((YOY.index >= AMOSTRA_INI) & fora_covid(YOY.index))[:, None] & ~np.isnan(Ymat)
Yz = np.where(Mamostra, Ymat, 0.0)


def corr_matrix(sr):
    """Correlação (27 séries x 13 defasagens) entre yoy_t e juro real_{t-k}, na amostra."""
    out_ = np.full((Ymat.shape[1], len(LAGS)), np.nan)
    for k in LAGS:
        x = np.full(len(sr), np.nan)
        x[k:] = sr[:len(sr) - k] if k else sr
        m = Mamostra & ~np.isnan(x)[:, None]
        n = m.sum(axis=0)
        xm = np.where(m, x[:, None], 0.0)
        ym = np.where(m, Yz, 0.0)
        mx, my = xm.sum(0) / n, ym.sum(0) / n
        dx, dy = np.where(m, xm - mx, 0), np.where(m, ym - my, 0)
        out_[:, k] = (dx * dy).sum(0) / np.sqrt((dx ** 2).sum(0) * (dy ** 2).sum(0))
    return out_


SR = mac.selic_real_aa.values   # mac e YOY compartilham o mesmo índice mensal (2002-01..)
assert (mac.index[:len(YOY)] == YOY.index).all()
SR = SR[:len(YOY)]
cor = pd.DataFrame(corr_matrix(SR), index=YOY.columns, columns=LAGS)
best_k = cor.idxmin(axis=1)     # sinal esperado: juro real alto -> produção menor
best_r = pd.Series({c: cor.loc[c, best_k[c]] for c in cor.index})


PERM_N = 2000
obs_min = cor.min(axis=1).values
cnt = np.zeros(len(cor))
for _ in range(PERM_N):
    rolled = np.roll(SR, int(RNG.integers(24, len(SR) - 24)))   # deslocamento circular: preserva autocorrelação
    cnt += corr_matrix(rolled).min(axis=1) <= obs_min           # e penaliza a escolha do melhor lag
pvals = pd.Series((cnt + 1) / (PERM_N + 1), index=cor.index)
p2 = pd.DataFrame({"atividade": nomes, "lag_otimo_meses": best_k, "r_melhor": best_r, "r_lag0": cor[0],
                   "p_perm": pvals}).sort_values("r_melhor")
p2.round(4).to_csv(PROC / "tab_P2_juro_real.csv", encoding="utf-8")
cor.round(3).to_csv(PROC / "tab_P2_correlacoes_por_lag.csv", encoding="utf-8")
sig = p2[p2.p_perm < 0.05]
R["P2"] = dict(
    perm_n=PERM_N, n_significativas=int(len(sig)), n_total=int(len(p2)), n_negativas=int((p2.r_melhor < 0).sum()),
    top=[(c, r.atividade, round(float(r.r_melhor), 3), int(r.lag_otimo_meses), round(float(r.p_perm), 3)) for c, r in p2.head(6).iterrows()],
    geral=dict(r=float(p2.loc["1", "r_melhor"]), lag=int(p2.loc["1", "lag_otimo_meses"]), p=float(p2.loc["1", "p_perm"])),
    transformacao=dict(r=float(p2.loc["3", "r_melhor"]), lag=int(p2.loc["3", "lag_otimo_meses"]), p=float(p2.loc["3", "p_perm"])),
    extrativas=dict(r=float(p2.loc["2", "r_melhor"]), lag=int(p2.loc["2", "lag_otimo_meses"]), p=float(p2.loc["2", "p_perm"])),
    lag_mediano_divisoes=float(p2[p2.index.str.startswith("3.")].lag_otimo_meses.median()),
    significativas=[(c, p2.loc[c, "atividade"], round(float(p2.loc[c, "r_melhor"]), 3), int(p2.loc[c, "lag_otimo_meses"]), round(float(p2.loc[c, "p_perm"]), 3)) for c in sig.index],
)


# ================================================================== P3: câmbio controlando o juro (OLS + HAC)
def ols_hac(y, X, L=12):
    X = np.column_stack([np.ones(len(X)), X])
    b = np.linalg.lstsq(X, y, rcond=None)[0]
    e = y - X @ b
    n, k = X.shape
    S = (X * e[:, None]).T @ (X * e[:, None])
    for l in range(1, L + 1):
        w = 1 - l / (L + 1)
        G = (X[l:] * e[l:, None]).T @ (X[:-l] * e[:-l, None])
        S += w * (G + G.T)
    XtXi = np.linalg.inv(X.T @ X)
    V = XtXi @ S @ XtXi * n / (n - k)
    se = np.sqrt(np.diag(V))
    r2 = 1 - (e @ e) / ((y - y.mean()) @ (y - y.mean()))
    return b, se, r2, n


rows = []
for c in YOY.columns:
    k = int(best_k[c])
    mac["sr_k"] = mac[f"sr_l{k}"]
    d = amostra(c, ["sr_k", "var_cambial_12m_pct"])
    b, se, r2, n = ols_hac(d.y.values, d[["sr_k", "var_cambial_12m_pct"]].values)
    rows.append(dict(codigo=c, atividade=nomes[c], lag_juro=k, beta_juro=b[1], se_juro=se[1], t_juro=b[1] / se[1],
                     beta_cambio=b[2], se_cambio=se[2], t_cambio=b[2] / se[2], r2=r2, n=n, sd_yoy=d.y.std()))
p3 = pd.DataFrame(rows).set_index("codigo")
p3.round(4).to_csv(PROC / "tab_P3_modelo.csv", encoding="utf-8")
lst = lambda d, n: [(c, r.atividade, round(r.beta_cambio, 3), round(r.t_cambio, 2)) for c, r in d.head(n).iterrows()]
R["P3"] = dict(
    cambio_pos_sig=[x for x in lst(p3.sort_values("t_cambio", ascending=False), 6) if x[3] > 1.96],
    cambio_neg_sig=[x for x in lst(p3.sort_values("t_cambio"), 6) if x[3] < -1.96],
    n_cambio_sig=int((p3.t_cambio.abs() > 1.96).sum()), n_juro_sig=int((p3.t_juro.abs() > 1.96).sum()), n_total=int(len(p3)),
    geral=dict(beta_juro=float(p3.loc["1", "beta_juro"]), t_juro=float(p3.loc["1", "t_juro"]),
               beta_cambio=float(p3.loc["1", "beta_cambio"]), t_cambio=float(p3.loc["1", "t_cambio"]),
               r2=float(p3.loc["1", "r2"]), lag=int(p3.loc["1", "lag_juro"])),
    r2_mediano=float(p3.r2.median()), r2_max=float(p3.r2.max()), r2_max_cod=p3.r2.idxmax(), r2_max_nome=nomes[p3.r2.idxmax()],
)

# ================================================================== P4: volatilidade
p4 = p3[["atividade", "sd_yoy"]].copy()
Y13 = YOY[YOY.index >= AMOSTRA_INI]
p4["pior_yoy_sem_covid_pct"] = Y13[fora_covid(Y13.index)].min()
p4["pior_yoy_com_covid_pct"] = Y13.min()
p4 = p4.sort_values("sd_yoy", ascending=False)
p4.round(2).to_csv(PROC / "tab_P4_volatilidade.csv", encoding="utf-8")
sd_div = p4[p4.index.str.startswith("3.")]
R["P4"] = dict(
    mais_volateis=[(c, r.atividade, round(r.sd_yoy, 1)) for c, r in sd_div.head(5).iterrows()],
    menos_volateis=[(c, r.atividade, round(r.sd_yoy, 1)) for c, r in sd_div.tail(5).iloc[::-1].iterrows()],
    geral=float(p4.loc["1", "sd_yoy"]), razao_max_min=float(sd_div.sd_yoy.max() / sd_div.sd_yoy.min()),
    corr_beta_vol=float(np.corrcoef(sd_div.sd_yoy, p3.loc[sd_div.index, "beta_juro"].abs())[0, 1]),
)

# ================================================================== P5: cenário de queda do juro real
sr_ser = macro.selic_real_aa.dropna()
R["P5_juro_real_atual_pct"] = float(sr_ser.iloc[-1])
R["P5_ult_mes_juro_real"] = str(sr_ser.index[-1].date())
R["P5_juro_real_media_hist_pct"] = float(sr_ser.mean())
R["P5_selic_atual"] = float(macro.selic_aa.dropna().iloc[-1])
R["P5_ipca12m_atual"] = float(macro.ipca_12m.dropna().iloc[-1])
DELTA = -3.0
p5 = p3[["atividade", "lag_juro", "beta_juro", "se_juro", "t_juro", "sd_yoy"]].copy()
p5["efeito_pp"] = p5.beta_juro * DELTA
p5["ic_inf"] = np.minimum((p5.beta_juro - 1.96 * p5.se_juro) * DELTA, (p5.beta_juro + 1.96 * p5.se_juro) * DELTA)
p5["ic_sup"] = np.maximum((p5.beta_juro - 1.96 * p5.se_juro) * DELTA, (p5.beta_juro + 1.96 * p5.se_juro) * DELTA)
p5["efeito_por_vol"] = p5.efeito_pp / p5.sd_yoy
p5["ic_exclui_zero"] = ((p5.ic_inf > 0) | (p5.ic_sup < 0)).astype(int)
p5 = p5.sort_values("efeito_pp", ascending=False)
p5.round(3).to_csv(PROC / "tab_P5_cenario.csv", encoding="utf-8")
sd5 = p5[p5.index.str.startswith("3.")]
ef = lambda c: dict(efeito=float(p5.loc[c, "efeito_pp"]), ic=[float(p5.loc[c, "ic_inf"]), float(p5.loc[c, "ic_sup"])])
R["P5"] = dict(
    delta_pp=DELTA, geral=ef("1"), transformacao=ef("3"), extrativas=ef("2"),
    top=[(c, r.atividade, round(r.efeito_pp, 2), [round(r.ic_inf, 2), round(r.ic_sup, 2)], int(r.lag_juro)) for c, r in sd5.head(5).iterrows()],
    n_ic_exclui_zero=int(sd5.ic_exclui_zero.sum()), n_efeito_positivo=int((sd5.efeito_pp > 0).sum()), n_div=int(len(sd5)),
    top_ratio=[(c, r.atividade, round(r.efeito_por_vol, 3)) for c, r in sd5.sort_values("efeito_por_vol", ascending=False).head(3).iterrows()],
)
json.dump(R, open(PROC / "resultados.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False, default=str)


# ================================================================== FIGURAS
def salvar(fig, nome):
    fig.tight_layout()
    fig.savefig(EVID / nome, dpi=150)
    plt.close(fig)


g = df[df.codigo == "1"].set_index("data")
fig, ax = plt.subplots(figsize=(9, 4.2))
ax.plot(g.index, g.indice, color=AZUL, lw=1.5, label="Produção industrial (índice, 2022=100)")
ax.set_ylabel("Índice PIM-PF (2022=100)", color=AZUL)
ax.axvspan(pd.Timestamp("2020-03-01"), pd.Timestamp("2021-06-01"), color=CINZA, alpha=.18, label="Período excluído (pandemia)")
ax2 = ax.twinx()
ax2.spines["right"].set_visible(True)
ax2.plot(macro.index, macro.selic_real_aa, color=LARANJA, lw=1.3, label="Juro real ex-post (% a.a.)")
ax2.set_ylabel("Juro real ex-post (% a.a.)", color=LARANJA)
h1, l1 = ax.get_legend_handles_labels()
h2, l2 = ax2.get_legend_handles_labels()
ax.legend(h1 + h2, l1 + l2, loc="lower left", fontsize=8, frameon=False)
ax.set_title("Indústria geral e juro real, 2002–2026")
salvar(fig, "fig1_industria_e_juro_real.png")

s = p1[p1.index.str.startswith("3.")].sort_values("razao_ult12m_2019")
fig, ax = plt.subplots(figsize=(9, 6.6))
vals = (s.razao_ult12m_2019 - 1) * 100
ax.barh(s.atividade.str.slice(0, 40), vals, color=[VERM if v < 0 else VERDE for v in vals])
ax.axvline(0, color="black", lw=.8)
ax.set_xlabel("Média dos últimos 12 meses vs. média de 2019 (%)")
ax.set_title("P1 — Produção atual vs. 2019, por divisão da indústria de transformação", fontsize=10)
for i, v in enumerate(vals):
    ax.text(v + (1.5 if v >= 0 else -1.5), i, f"{v:+.0f}%", va="center", ha="left" if v >= 0 else "right", fontsize=7)
ax.margins(x=.12)
ax.tick_params(axis="y", labelsize=8)
salvar(fig, "fig2_P1_recuperacao_pre_pandemia.png")

h = cor.loc[[c for c in cor.index if c.startswith("3.")]].copy()
h = h.loc[h.min(axis=1).sort_values().index]
fig, ax = plt.subplots(figsize=(9, 6.6))
im = ax.imshow(h.values, cmap="RdBu", vmin=-.6, vmax=.6, aspect="auto")
ax.set_yticks(range(len(h)))
ax.set_yticklabels([nomes[c][:40] for c in h.index], fontsize=8)
ax.set_xticks(range(13))
ax.set_xticklabels(LAGS)
ax.set_xlabel("Defasagem do juro real (meses): juro em t−k vs. crescimento anual em t")
ax.set_title("P2 — Correlação entre juro real e crescimento anual (□ = defasagem de maior efeito)", fontsize=10)
fig.colorbar(im, ax=ax).set_label("Correlação de Pearson")
for i, c in enumerate(h.index):
    ax.plot(int(best_k[c]), i, marker="s", mfc="none", mec="black", ms=7)
salvar(fig, "fig3_P2_correlacao_por_defasagem.png")

s = p3[p3.index.str.startswith("3.")].sort_values("beta_cambio")
fig, axs = plt.subplots(1, 2, figsize=(11, 6.6), sharey=True)
for ax, col, ttl in [(axs[0], "juro", "Efeito de +1 p.p. de juro real\n(no crescimento anual, p.p.)"),
                     (axs[1], "cambio", "Efeito de +1% de desvalorização cambial 12m\n(no crescimento anual, p.p.)")]:
    b, se = s[f"beta_{col}"], s[f"se_{col}"]
    cores = [AZUL if abs(bi / si) > 1.96 else CINZA for bi, si in zip(b, se)]
    ax.errorbar(b, range(len(s)), xerr=1.96 * se, fmt="none", ecolor=CINZA, lw=1)
    ax.scatter(b, range(len(s)), c=cores, s=22, zorder=3)
    ax.axvline(0, color="black", lw=.8)
    ax.set_title(ttl, fontsize=9)
axs[0].set_yticks(range(len(s)))
axs[0].set_yticklabels([nomes[c][:40] for c in s.index], fontsize=8)
fig.suptitle("P3 — Coeficientes do modelo (azul = significativo a 5%; IC 95% robusto HAC)", fontweight="bold", fontsize=10)
salvar(fig, "fig4_P3_coeficientes.png")

s = p5[p5.index.str.startswith("3.")]
fig, ax = plt.subplots(figsize=(9, 5.6))
ax.scatter(s.sd_yoy, s.efeito_pp, c=[AZUL if v else CINZA for v in s.ic_exclui_zero], s=40, zorder=3)
for c, r in s.iterrows():
    if abs(r.efeito_pp) > 1.4 or r.sd_yoy > 11:
        ax.annotate(r.atividade[:32], (r.sd_yoy, r.efeito_pp), fontsize=7, xytext=(4, 3), textcoords="offset points")
ax.axhline(0, color="black", lw=.8)
ax.set_xlabel("Volatilidade (desvio-padrão do crescimento anual, p.p.)")
ax.set_ylabel("Efeito estimado de −3 p.p. de juro real (p.p.)")
ax.set_title("P4/P5 — Ganho esperado com queda do juro vs. volatilidade (azul: IC 95% exclui zero)", fontsize=10)
salvar(fig, "fig5_P4_P5_sensibilidade_volatilidade.png")

aus = df.assign(aus=df.indice.isna()).pivot(index="codigo", columns="data", values="aus")
lin = aus.loc[[c for c in aus.index if aus.loc[c].any()]]
fig, ax = plt.subplots(figsize=(9, 2.6))
ax.imshow(lin.values.astype(int), aspect="auto", cmap="Reds", interpolation="nearest",
          extent=[0, len(lin.columns), len(lin), 0])
ax.set_yticks(np.arange(len(lin)) + .5)
ax.set_yticklabels([f"{c} {nomes[c][:22]}" for c in lin.index], fontsize=8)
anos = list(range(2002, 2027, 4))
ax.set_xticks([(pd.Timestamp(f"{a}-01-01") - lin.columns[0]).days / 30.44 for a in anos])
ax.set_xticklabels(anos)
ax.set_title("Qualidade — meses sem informação no IBGE (vermelho = ausente)", fontsize=10)
salvar(fig, "fig6_qualidade_ausencias.png")

fig, ax = plt.subplots(figsize=(10, 5.6))
ax.axis("off")
ax.set_xlim(0, 10)
ax.set_ylim(-0.4, 6)


def caixa(x, y, w, h_, titulo, campos, cor):
    ax.add_patch(plt.Rectangle((x, y), w, h_, fc="white", ec=cor, lw=2))
    ax.add_patch(plt.Rectangle((x, y + h_ - .5), w, .5, fc=cor, ec=cor))
    ax.text(x + w / 2, y + h_ - .25, titulo, ha="center", va="center", color="white", fontweight="bold", fontsize=10)
    for i, c in enumerate(campos):
        ax.text(x + .12, y + h_ - .8 - i * .32, c, fontsize=8, va="center", family="monospace")


caixa(3.6, 2.3, 2.8, 2.5, "fato_producao", ["PK/FK sk_tempo", "PK/FK sk_atividade", "indice", "var_yoy_pct", "flag_indice_ausente"], AZUL)
caixa(0.2, 3.4, 2.6, 2.4, "dim_tempo", ["PK sk_tempo (AAAAMM)", "data", "ano, mes, trimestre", "nome_mes", "periodo_covid"], LARANJA)
caixa(7.2, 3.4, 2.6, 2.4, "dim_atividade", ["PK sk_atividade", "codigo (CNAE)", "atividade", "atividade_curta", "nivel, secao_pai"], LARANJA)
caixa(3.6, -0.2, 2.8, 2.3, "fato_macro", ["PK/FK sk_tempo", "selic_aa, ipca_mensal", "ipca_12m, dolar_medio", "selic_real_aa", "var_cambial_12m_pct"], VERDE)
for (x1, y1, x2, y2) in [(2.8, 4.5, 3.6, 4.0), (7.2, 4.5, 6.4, 4.0), (1.5, 3.4, 3.7, 1.0)]:
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=CINZA, lw=1.5))
ax.set_title("Modelo dimensional (constelação de fatos: 2 fatos, 2 dimensões)", fontweight="bold")
(ROOT / "catalogo").mkdir(exist_ok=True)
fig.savefig(ROOT / "catalogo" / "diagrama_estrela.png", dpi=150, bbox_inches="tight")
plt.close(fig)

print(json.dumps(R, indent=1, ensure_ascii=False, default=str))
