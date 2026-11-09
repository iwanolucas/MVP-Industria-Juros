"""Gera README.md e o relatório Word a partir dos mesmos blocos de conteúdo e de data/processed/resultados.json.

Uso: python scripts/gerar_relatorio.py [caminho_docx]
"""
import json
import re
import sys
from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
PROC, EVID = ROOT / "data" / "processed", ROOT / "evidencias"
DOCX_OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "Relatorio_MVP_Industria_Juros_Lucas_Iwano.docx"
R = json.loads((PROC / "resultados.json").read_text(encoding="utf-8"))
LOG = json.loads((PROC / "log_etl.json").read_text(encoding="utf-8"))
MAN = json.loads((ROOT / "data" / "raw" / "_manifesto_coleta.json").read_text(encoding="utf-8"))
CAT = pd.read_csv(ROOT / "catalogo" / "catalogo_dados.csv")
P1 = pd.read_csv(PROC / "tab_P1_folga.csv", dtype={"codigo": str})
P5 = pd.read_csv(PROC / "tab_P3a_juro_cenario.csv", dtype={"codigo": str})
MAPA = pd.read_csv(PROC / "tab_P5_mapa_risco.csv", dtype={"codigo": str})
NUVEM = json.loads((EVID / "nuvem_status.json").read_text(encoding="utf-8")) if (EVID / "nuvem_status.json").exists() else {"executado": False}
QATTR = pd.read_csv(PROC / "tab_qualidade_atributos.csv")
REPO = "https://github.com/iwanolucas/MVP-Industria-Juros"
DISCIPLINA = "Sistemas de Suporte à Decisão (SSD)"
ALUNO = "Lucas Vilas Boas Iwano — matrícula 221021017"


def _renumera_nuvem(txt):
    """As figuras da nuvem já vêm numeradas (2–10) em evidencias/nuvem_status.json."""
    return txt


if NUVEM.get("executado"):
    NUVEM["paragrafos"] = [_renumera_nuvem(x) for x in NUVEM.get("paragrafos", [])]
    NUVEM["figuras"] = [[a, _renumera_nuvem(l)] for a, l in NUVEM.get("figuras", [])]


def f(x, d=1):
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x, d=1):
    return f(x, d) + "%"


def nome(c):
    return P1.set_index("codigo").atividade[c]


B = []  # blocos: (tipo, ...)
h1 = lambda t: B.append(("h1", t))
h2 = lambda t: B.append(("h2", t))
p = lambda t: B.append(("p", t))
bl = lambda items: B.append(("ul", items))
tb = lambda head, rows, widths=None: B.append(("table", head, rows, widths))
im = lambda arq, leg: B.append(("img", arq, leg))

P1r, P2r, P3r, P4r, P5r = R["FOLGA"], R["JURO_NIVEL"], R["CAMBIO"], R["INSTABILIDADE"], R["JURO_CENARIO"]

# =====================================================================================================
_C, _M = R["CICLOS"], R["MAPA"]
h1("Resumo")
p("Pergunta: qual é o risco de cada divisão da indústria de transformação brasileira hoje, e de onde ele vem? O destinatário é a área de crédito de um "
  "banco de desenvolvimento, que decide limites e provisões por setor.")
p("O que foi feito: um pipeline em nuvem (Databricks Free Edition, arquitetura medallion, tabelas Delta) que integra a produção industrial do IBGE "
  "(PIM-PF, 27 atividades) às séries de Selic, IPCA e câmbio do Banco Central, de 2002 a 2026, em um esquema dimensional com catálogo de dados e "
  "verificação de qualidade atributo a atributo. A análise mede quatro fontes de risco por divisão e as combina em um mapa de risco.")
bl([
    f"Folga (P1): {P1r['abaixo']} das {P1r['n_divisoes']} divisões ainda produzem abaixo da média de 2019, embora a indústria geral esteja {f((P1r['geral_razao'] - 1) * 100)}% acima.",
    f"Instabilidade (P2): o crescimento anual de Fumo oscila {f(P4r['razao_max_min'], 1)} vezes mais que o de Celulose e papel.",
    f"Exposição ao juro (P3): o nível do juro real não diferencia os setores; a direção da Selic, sim. Em ciclos de alta, {_C['completo']['n_negativas']} de "
    f"{_C['completo']['n_div']} divisões crescem menos. O sinal se repetiu na validação fora da amostra (2003–2012), mas sem significância setor a setor.",
    f"Exposição ao câmbio (P4): a desvalorização acompanha crescimento menor em {P3r['n_cambio_sig']} atividades, sobretudo nas que importam componentes.",
    f"Mapa de risco (P5): Informática e eletrônicos, Veículos e Impressão lideram o ranking, cada uma com três das quatro fontes de risco; o ranking é estável "
    f"a mudanças de critério (correlação de postos de {f(min(v['spearman'] for v in _M['deixa_uma_fora'].values()), 2)} a {f(_M['spearman_indice_por_postos'], 2)}).",
])
p("Limitação principal: o índice mede sinais de fragilidade setorial, mas ainda não foi validado contra o risco de crédito observado (inadimplência por setor). "
  "Até essa validação, deve ser usado como triagem e para indicar o que monitorar em cada setor, não como modelo de risco. O mapa completo está na Seção 5.6.")

# =====================================================================================================
h1("1. Objetivo")
h2("1.1 Problema")
p("A área de crédito de um banco de desenvolvimento precisa decidir, setor por setor da indústria, quanto emprestar e quanto provisionar. "
  "O mesmo vale para um gestor industrial que avalia fornecedores e clientes, ou para um investidor que monta uma carteira. Hoje o juro real "
  "brasileiro está em 9,3% a.a. (agosto/2026, pelos dados deste trabalho), bem acima da média de 5,5% desde 2002, e a pergunta que todos fazem é a mesma: "
  "quais setores são mais arriscados agora, e por quê?")
p("O MVP constrói um pipeline de dados na nuvem que integra duas fontes públicas, a Pesquisa Industrial Mensal – Produção Física (PIM-PF/IBGE), com 27 "
  "atividades industriais, e as séries do Banco Central (Selic, IPCA e dólar). Com isso produz um mapa de risco setorial: um índice por divisão da indústria de "
  "transformação que combina quatro fontes de risco medidas nos dados, e que diz não só quem é mais arriscado, mas de onde vem o risco de cada um.")
h2("1.2 Pergunta central e perguntas de negócio")
p("Pergunta central: qual é o risco de cada divisão da indústria de transformação hoje, e de onde ele vem? Cada pergunta abaixo mede uma dimensão do risco; a última as combina.")
tb(["#", "Dimensão", "Pergunta", "Decisão a que se liga"], [
    ["P1", "Folga", "Quais divisões ainda produzem abaixo da média de 2019, e em quantos meses cada uma voltou ao patamar pré-pandemia?", "Demanda estruturalmente fraca: risco de receita do tomador."],
    ["P2", "Instabilidade", "Quanto oscila o crescimento anual de cada divisão?", "Tamanho da provisão e do capital de giro exigido."],
    ["P3", "Exposição ao juro", "Quais divisões crescem menos quando o juro sobe? Responde-se pelo nível do juro real (com defasagem de 0 a 12 meses e um cenário de −3 p.p.) e pela direção da Selic (ciclos de alta vs. corte), com validação fora da amostra.", "Revisar limites quando o Copom inicia um ciclo de alta."],
    ["P4", "Exposição ao câmbio", "Controlado o juro, quais divisões perdem com a desvalorização do real?", "Exigir proteção cambial ou cláusulas de ajuste."],
    ["P5", "Síntese", "Combinando as quatro dimensões, qual é o ranking de risco das divisões, e quão estável ele é a mudanças de critério?", "Priorização da carteira e faixas de limite (alto, médio, baixo)."],
])
h2("1.3 Hipóteses")
bl([
    "H1 — Concentração. O risco não se distribui por igual: as divisões do topo do ranking acumulam várias fontes de risco ao mesmo tempo.",
    "H2 — Juro. Divisões dependentes de crédito (bens duráveis e ligados à construção) crescem menos quando o juro sobe.",
    "H3 — Câmbio. A desvalorização do real favorece as divisões exportadoras, depois de controlado o juro.",
    "H4 — Recuperação. A recuperação pós-pandemia foi desigual: o agregado voltou ao nível de 2019, mas há divisões abaixo dele.",
])
h2("1.4 Evolução do objetivo")
p("O problema original, a relação entre juros, câmbio e produção industrial por setor, foi definido antes da escolha das bases. A primeira versão do trabalho "
  "(setembro de 2026) tinha cinco perguntas independentes: recuperação, sensibilidade ao juro, câmbio, volatilidade e um cenário de corte de juros. A revisão de "
  "novembro de 2026, anterior à entrega, reorganizou-as como dimensões de uma pergunta única, sem remover nenhuma: a recuperação virou P1, a volatilidade virou P2, "
  "a sensibilidade ao juro e o cenário viraram a análise de nível do P3, e o câmbio virou P4. São novas a síntese (P5) e a análise de ciclos de juros dentro do P3.")
p("A análise de ciclos surgiu de uma exploração feita depois de a sensibilidade ao nível do juro dar resultado nulo: os ciclos foram examinados primeiro em 2013–2026. "
  "Como a hipótese nasceu desses dados, ela foi testada em um período independente, 2003–2012, com a definição de ciclo e o critério de confirmação declarados antes "
  "do teste (Seção 5.4). Isso corresponde a uma segunda volta do ciclo construir–medir–aprender descrito no enunciado do MVP.")

# =====================================================================================================
h1("2. Coleta")
h2("2.1 Fontes")
tb(["Arquivo bruto", "Origem", "Registros", "Tamanho", "Formato original"],
   [[m["arquivo"], m["url"].replace("https://", "")[:70] + ("…" if len(m["url"]) > 78 else ""), f(m["registros"], 0), f(m["bytes"] / 1024, 0) + " KB", "JSON"] for m in MAN])
p(f"Coleta realizada em {MAN[0]['coletado_em_utc'][:10].split('-')[2]}/{MAN[0]['coletado_em_utc'][:10].split('-')[1]}/{MAN[0]['coletado_em_utc'][:4]} "
  "(UTC) pelo script scripts/coleta.py, que grava também data/raw/_manifesto_coleta.json com URL, data, volume, formato e hash SHA-256 de cada arquivo. "
  "As APIs são públicas e não exigem chave. O script repete a requisição até 5 vezes, porque a API do BCB devolveu corpo vazio de forma intermitente durante o desenvolvimento.")
p("Não houve web scraping: as duas fontes oferecem API oficial. A tabela 8888 da SIDRA traz o número-índice de produção física com base 2022 = 100, "
  "sem ajuste sazonal, para o Brasil, de janeiro/2002 a julho/2026 (295 meses × 27 atividades). As quatro séries do SGS são mensais: "
  "Selic acumulada no mês anualizada (4189), IPCA mensal (433), IPCA acumulado em 12 meses (13522) e dólar médio de venda (3698).")
h2("2.2 Persistência na nuvem")
if NUVEM.get("executado"):
    p(NUVEM.get("texto_persistencia", ""))
else:
    p("Os arquivos brutos ficam versionados no repositório (data/raw). A persistência na plataforma de nuvem (Databricks, Volume do Unity Catalog e "
      "tabelas Delta) é feita pelos notebooks 01 e 02, e o status da execução consta na Seção 4.3.")

# =====================================================================================================
h1("3. Modelagem")
h2("3.1 Modelo de dados")
p("Adotou-se um esquema dimensional do tipo constelação de fatos, com duas tabelas fato que compartilham a dimensão tempo:")
bl([
    "fato_producao: uma linha por mês e atividade (7.965 linhas): índice de produção, variação anual e indicador de ausência.",
    "fato_macro: uma linha por mês (297 linhas): Selic, IPCA, dólar e as métricas derivadas (juro real e variação cambial de 12 meses).",
    "dim_tempo: 297 meses, de janeiro/2002 a setembro/2026, com ano, trimestre e marcador de pandemia.",
    "dim_atividade: 27 atividades com código CNAE, nível hierárquico (geral, seção, divisão) e nome abreviado.",
])
p("A escolha se justifica por três razões. As duas fontes têm o mesmo grão temporal (mês), o que torna o tempo a dimensão natural de integração. "
  "As métricas macro pertencem ao mês, não à atividade, e repeti-las em cada linha de produção multiplicaria por 27 o volume e o risco de inconsistência. "
  "Por fim, o esquema permite responder às perguntas com joins simples de SQL.")
p("Sobre o esquema, a análise grava uma tabela de consumo, mapa_risco: uma linha por divisão da transformação, com as quatro dimensões de risco, o índice, "
  "a posição no ranking e a faixa. Ela referencia dim_atividade e é gravada em SQLite na execução local e como tabela Delta pelo notebook 03 no Databricks.")
im(ROOT / "catalogo" / "diagrama_estrela.png", "Figura 1 — Modelo dimensional do MVP: constelação de fatos com dimensão tempo compartilhada (catalogo/diagrama_estrela.png).")
h2("3.2 Catálogo de dados")
p("Cada atributo tem dois domínios. O domínio esperado é declarado a priori, pelo significado do dado (por exemplo, número-índice estritamente positivo; "
  "variação percentual nunca abaixo de −100%; Selic entre 0 e 50% a.a.), e está codificado em scripts/dominios.py. O domínio observado é lido da base carregada. "
  "A análise de qualidade (Seção 5.1) confere, atributo a atributo, se o observado respeita o esperado. O catálogo completo, com descrição, obrigatoriedade e "
  "linhagem de cada atributo, está em catalogo/catalogo_dados.md e .csv.")
tb(["Tabela", "Atributo", "Tipo", "Descrição", "Domínio esperado", "Domínio observado", "Nulos", "Linhagem"],
   [[r.tabela, r.atributo, r.tipo, r.descricao, r.dominio_esperado, r.dominio_observado, str(r.nulos_observados), r.linhagem] for r in CAT.itertuples()])
p("Sobre a obrigatoriedade: os únicos nulos com significado próprio são (a) o índice das divisões 3.18 (Impressão) e 3.33 (Manutenção), que o IBGE só "
  "publica a partir de 2012, (b) os 12 primeiros meses de variação anual e cambial, que dependem de um ano de histórico, e (c) os campos do mês corrente do BCB "
  "(setembro/2026), ainda sem divulgação completa. Nenhum nulo foi imputado.")

# =====================================================================================================
h1("4. Carga (ETL)")
h2("4.1 Arquitetura do pipeline")
p("O pipeline segue a arquitetura em camadas (medallion) e é executado por três notebooks Databricks, cada um um invólucro fino sobre um script Python versionado. "
  "O mesmo código roda localmente (SQLite) e na nuvem (tabelas Delta), o que permitiu validar a lógica antes de subir à plataforma.")
tb(["Camada", "Conteúdo", "Onde", "Código"], [
    ["Bronze", "JSON bruto das APIs, sem alteração", "Volume raw (Unity Catalog) / data/raw", "notebooks/01_coleta_bronze.py → scripts/coleta.py"],
    ["Silver", "Tabelas limpas e tipadas (datas, códigos, nulos)", "Memória do ETL", "scripts/etl.py (R1 a R6)"],
    ["Gold", "Esquema estrela em Delta", "workspace.industria_juros.*", "notebooks/02_etl_silver_gold.py → scripts/etl.py (R7 a R9)"],
    ["Consumo", "Consultas SQL, testes e gráficos", "Notebook 03", "notebooks/03_analise.py → scripts/analise.py"],
])
h2("4.2 Regras de negócio da transformação")
tb(["Regra", "Descrição", "Efeito medido"], [
    ["R1", "Mês em português (\"janeiro 2002\") convertido em data (1º dia do mês) e chave AAAAMM.", "295 meses PIM-PF e 297 meses BCB alinhados."],
    ["R2", "Código CNAE separado do nome da atividade.", "27 atividades: 1 geral, 2 seções e 24 divisões."],
    ["R3", "\"-\" (sem informação) vira NULL; nunca imputado.", f"{LOG['pim_valores_ausentes_R3']} valores nulos (2 divisões × 120 meses)."],
    ["R4", "Datas do BCB (dd/mm/aaaa) normalizadas para o 1º dia do mês; valores em ponto flutuante.", "Junção exata por mês."],
    ["R5", "Duplicatas pela chave natural (mês, atividade) removidas, mantendo a primeira.", f"{LOG['pim_duplicatas_removidas_R5']} duplicatas."],
    ["R6", "Variação anual = índice ÷ índice de 12 meses antes − 1, por atividade.", "564 nulos estruturais (12 meses iniciais e ausências)."],
    ["R7", "Juro real ex-post = (1 + Selic a.a.) ÷ (1 + IPCA 12m) − 1.", "Faixa observada de −4,4% a 13,0% a.a."],
    ["R8", "Variação cambial 12m = dólar médio ÷ dólar médio de 12 meses antes − 1.", "Positivo = real desvalorizado."],
    ["R9", "Meses só do BCB (sem PIM-PF) permanecem na fato_macro com flag_tem_producao = 0.", f"{LOG['macro_meses_sem_producao_R9']} meses (ago. e set./2026)."],
])
p("Foram verificadas as integridades referencial (toda chave das fatos existe nas dimensões) e de unicidade (nenhuma duplicata na chave composta), com asserções no ETL: o script falha se alguma delas for violada.")
h2("4.3 Execução na nuvem e persistência")
if NUVEM.get("executado"):
    for par in NUVEM.get("paragrafos", []):
        p(par)
    for arq, leg in NUVEM.get("figuras", []):
        im(ROOT / "evidencias" / arq, leg)
else:
    p("Status: os notebooks Databricks (notebooks/01, 02 e 03) foram escritos e a lógica que eles executam foi validada localmente, com o mesmo código e as mesmas "
      "consultas SQL (o resultado da consulta P1 em SQL bate com o do pandas, diferença 0,0). **A execução dentro do Databricks ainda não foi realizada nesta versão** "
      "porque exige login da própria conta do aluno na plataforma, e não há evidência de nuvem (capturas de tela) neste relatório. Os passos para executar estão no README: "
      "criar a conta gratuita Databricks Free Edition, criar uma Git folder apontando para o repositório e executar os três notebooks em ordem. "
      "Ao final, o notebook 02 grava as quatro tabelas Delta e o comando DESCRIBE HISTORY comprova a persistência.")
h2("4.4 Uso de recursos e custo de operação")
vol_bruto = sum(m["bytes"] for m in MAN) / 1e6  # MB decimais, como na Seção 6
p(f"O enunciado pede evidência de viabilidade financeira: uso de recursos compatível com o problema e custo de operação estimado. O volume é pequeno: "
  f"{f(vol_bruto, 1)} MB de JSON bruto e {f(sum(v for k, v in LOG.items() if k.startswith('gold_')), 0)} linhas nas quatro tabelas Delta. "
  "Uma execução completa (três notebooks) roda em compute serverless de menor porte, sem cluster dedicado.")
tb(["Item", "Neste MVP", "Operação contínua (estimativa)"], [
    ["Plataforma", "Databricks Free Edition", "Workspace pago (Premium), job serverless"],
    ["Computação", "R$ 0 (cota gratuita)", "Ordem de 1 DBU por execução × US$ 0,35/DBU (preço de lista de Jobs Serverless, AWS Premium, conferido em nov/2026) ≈ US$ 0,35 por mês, com uma execução mensal"],
    ["Armazenamento", "R$ 0", f"{f(vol_bruto, 1)} MB brutos + tabelas Delta: custo de armazenamento desprezível (centavos por mês)"],
    ["Coleta", "APIs públicas, sem chave e sem custo", "Idem"],
])
p("O consumo de DBU não foi medido: o Free Edition não expõe esse número, e a linha de 1 DBU por execução é uma ordem de grandeza para três notebooks curtos sobre "
  "menos de 2 MB, não uma medição. Mesmo multiplicada por dez, a operação mensal fica abaixo de US$ 5. Conclusão: o custo não é obstáculo. A restrição real "
  "observada foi técnica: o Free Edition não acessa a internet, o que obrigou a separar a coleta (local) da persistência (nuvem), como descrito na Seção 4.3.")

# =====================================================================================================
h1("5. Análise")
h2("5.1 Qualidade dos dados")
p(f"A qualidade foi verificada em dois níveis. Primeiro, atributo a atributo: para cada um dos {R['q_atributos_total']} atributos das quatro tabelas, mediram-se "
  "completude, número de valores distintos e aderência ao domínio esperado declarado no catálogo (Seção 3.2). Depois, nas seis dimensões usuais, com testes "
  "que cruzam atributos e fontes. Todos os números vêm do script de análise (data/processed/resultados.json e tab_qualidade_atributos.csv).")
tb(["Tabela", "Atributo", "Completude", "Nulos", "Distintos", "Fora do domínio esperado"],
   [[r.tabela, r.atributo, f(r.completude_pct, 1) + "%", f(r.nulos, 0), f(r.distintos, 0), f(r.fora_dominio, 0)] for r in QATTR.itertuples()])
_qa = lambda t, c: QATTR[(QATTR.tabela == t) & (QATTR.atributo == c)].iloc[0]
pk_dup = sum(R["q_pk_duplicadas"].values())
fk_orf = sum(R["q_fk_orfas"].values())
p(f"Resultado atributo a atributo: {R['q_atributos_fora_dominio']} dos {R['q_atributos_total']} atributos têm valores fora do domínio esperado, e {R['q_atributos_com_nulos']} "
  f"têm nulos, todos explicados na Seção 3.2 (séries que o IBGE só publica a partir de 2012, variações que dependem de 12 meses de histórico e o mês corrente do BCB). "
  f"As chaves primárias das quatro tabelas não têm duplicatas ({pk_dup} no total) e não há chave estrangeira órfã ({fk_orf} no total). "
  f"O índice tem {f(_qa('fato_producao', 'indice').distintos, 0)} valores distintos em {f(_qa('fato_producao', 'indice').linhas, 0)} linhas e a Selic, "
  f"{f(_qa('fato_macro', 'selic_aa').distintos, 0)} em {f(_qa('fato_macro', 'selic_aa').linhas, 0)} meses; repetições são esperadas em séries arredondadas "
  "a duas casas e não indicam duplicação, já descartada pelo teste de chave.")
tb(["Dimensão", "Verificação", "Resultado", "Tratamento"], [
    ["Completude", "Nulos por atributo",
     f"Índice: {R['q_indice_ausentes_total']} nulos, todos nas divisões 3.18 e 3.33 entre jan/2002 e dez/2011. IPCA e dólar: 1 nulo cada (set./2026).",
     "Não imputados. As séries são usadas só a partir de 2013, período em que todas as 27 estão completas."],
    ["Unicidade", "Duplicatas em (mês, atividade)", f"{R['q_duplicatas_chave']} duplicatas; {R['q_lacunas_temporais']} lacunas de mês em qualquer série.", "Nenhum."],
    ["Consistência", "Variação anual recalculada; IPCA 12m oficial vs. composição do IPCA mensal; indústria geral vs. seções",
     f"Diferença máxima da variação anual: {R['q_consist_yoy_max_diff']:.0e} p.p.; IPCA 12m: diferença média de {f(R['q_ipca12m_vs_composto_medio_pp'], 4)} p.p. (máxima {f(R['q_ipca12m_vs_composto_max_diff_pp'], 3)} p.p., arredondamento); a indústria geral fica entre as seções em {f(R['q_geral_entre_secoes_pct'], 0)}% dos meses.",
     "Nenhum. Fontes coerentes entre si."],
    ["Conformidade", "Aderência ao domínio esperado do catálogo",
     f"{R['q_atributos_fora_dominio']} atributos fora do domínio (tabela acima). Índice > 0 em 100% das linhas (mín. {f(R['q_indice_min_max_global'][0], 1)}; máx. {f(R['q_indice_min_max_global'][1], 1)}). Selic {f(R['q_macro_dominios']['selic_aa'][0], 1)}–{f(R['q_macro_dominios']['selic_aa'][1], 1)}% a.a.; dólar R$ {f(R['q_macro_dominios']['dolar_medio'][0], 2)}–{f(R['q_macro_dominios']['dolar_medio'][1], 2)}.",
     "Nenhum. Todos plausíveis."],
    ["Acurácia", "Outliers da variação anual (z robusto, em módulo, acima de 5)",
     f"{R['q_outliers_yoy_total']} pontos, dos quais {R['q_outliers_yoy_em_pandemia_2020_21']} em mar/2020–jun/2021 (choque e rebote: maior valor, veículos em abr/2021, +{f(R['q_outliers_yoy_top'][0]['var_yoy_pct'], 0)}% sobre a base do lockdown) e {R['q_outliers_yoy_fora_pandemia']} fora dele.",
     "A janela de pandemia é excluída das estatísticas (P2 a P4); os 10 pontos restantes são mantidos (variações reais de setores voláteis)."],
    ["Atualidade", "Defasagem entre fontes", f"PIM-PF vai até jul/2026; o BCB, até {R['q_macro_ultimo_mes'][:7].replace('-', '/')} (defasagem de {R['q_defasagem_pim_vs_macro_meses']} meses). O último mês do BCB é parcial.",
     "Junção por interseção (R9); o cenário de corte de juros (P3) usa o último juro real completo (ago./2026)."],
])
im(EVID / "fig_qualidade_ausencias.png", "Figura 11 — Meses sem informação no IBGE: apenas as divisões 3.18 e 3.33, antes de 2012.")
p("Ressalva importante: o índice não tem ajuste sazonal. A série industrial oscila fortemente entre meses por sazonalidade (Figura 12), o que torna inadequada a comparação mês a mês. "
  "Por isso toda a análise usa variação contra o mesmo mês do ano anterior, que elimina a sazonalidade, e médias de 12 meses.")
im(EVID / "fig_serie_industria_juro_real.png", "Figura 12 — Produção industrial (índice sem ajuste sazonal) e juro real ex-post, 2002–2026.")
p(f"Amostra de análise. Para instabilidade (P2), nível do juro (P3) e câmbio (P4) usa-se janeiro/2013 a julho/2026, excluindo mar/2020–jun/2021: {R['amostra_meses']} meses, comum às 27 atividades. "
  "O corte em 2013 é o primeiro mês em que as duas divisões de série curta têm variação anual; a exclusão da pandemia evita que um único choque de +900% domine correlações e regressões. "
  "A análise de ciclos de juros (P3) usa também 2003–2012, para a validação fora da amostra, com as 22 divisões que já eram publicadas.")

h2("5.2 P1 — Folga: recuperação em relação a 2019")
p(f"O agregado voltou: a indústria geral produz hoje (média dos últimos 12 meses) {f((P1r['geral_razao'] - 1) * 100)}% acima da média de 2019, com queda máxima de "
  f"{f(abs(P1r['geral_queda_2020']), 0)}% no fundo de 2020 e retorno sustentado ao patamar de 2019 em {f(P1r['geral_meses'], 0)} meses. As extrativas estão "
  f"{f((P1r['extrativas'] - 1) * 100)}% acima, e a indústria de transformação, {f((P1r['transformacao'] - 1) * 100)}% acima. "
  f"A média, porém, esconde a divisão: das {P1r['n_divisoes']} divisões da transformação, {P1r['abaixo']} ainda estão abaixo de 2019 e {P1r['acima']} acima (Figura 13).")
im(EVID / "fig_P1_folga_vs_2019.png", "Figura 13 — Folga: produção dos últimos 12 meses vs. média de 2019, por divisão (P1).")
sel = P1[P1.codigo.str.startswith("3.")].sort_values("razao_ult12m_2019")
linhas = pd.concat([sel.head(5), sel.tail(5)])
tb(["Cód.", "Divisão", "Atual vs. 2019", "Queda máx. 2020", "Meses p/ recuperar"],
   [[r.codigo, r.atividade, f"{(r.razao_ult12m_2019 - 1) * 100:+.1f}%".replace(".", ","), f"{r.queda_maxima_2020_pct:.0f}%".replace(".", ","),
     "não recuperou" if pd.isna(r.meses_ate_recuperar) else f"{int(r.meses_ate_recuperar)}"] for r in linhas.itertuples()])
p("Resposta a P1. As divisões com mais folga são Impressão (−33%), Vestuário (−27%), Móveis (−17%), Couro e calçados (−16%) e Produtos diversos (−16%): atividades "
  "intensivas em mão de obra e ligadas ao consumo das famílias e à mídia física. Quatro divisões (Impressão, Vestuário, Produtos diversos e Manutenção) nunca tiveram três "
  "meses seguidos acima da média de 2019 desde o choque. No outro extremo estão Fumo (+38%), Derivados de petróleo (+15%), Máquinas e equipamentos (+11%) e Outros "
  "equipamentos de transporte (+10%). H4 confirmada: a recuperação foi desigual, e o agregado (+3,0%) esconde 13 divisões abaixo do nível pré-pandemia. "
  "Cautela: 2019 foi um ano de crescimento fraco, então \"acima de 2019\" não significa \"acima da tendência\".")

h2("5.3 P2 — Instabilidade")
sd = P4r
p("A instabilidade é o desvio-padrão do crescimento anual na amostra de análise (2013–2026, sem a pandemia). As divisões variam mais de quatro vezes entre si: "
  f"Fumo ({f(sd['mais_volateis'][0][2], 1)} p.p.), Informática ({f(sd['mais_volateis'][1][2], 1)}), Veículos ({f(sd['mais_volateis'][2][2], 1)}) e Impressão ({f(sd['mais_volateis'][3][2], 1)}) "
  f"são as mais instáveis; Celulose e papel ({f(sd['menos_volateis'][0][2], 1)}), Químicos ({f(sd['menos_volateis'][1][2], 1)}) e Minerais não metálicos ({f(sd['menos_volateis'][2][2], 1)}) as mais estáveis. "
  f"A indústria geral, por diversificação, tem {f(sd['geral'], 1)} p.p., no nível da divisão mais estável.")
p(f"Resposta a P2. A razão entre a divisão mais e a menos instável é de {f(sd['razao_max_min'], 1)} vezes. O pior crescimento anual de Veículos é −39% sem a pandemia e −92% com ela; "
  "o de Celulose e papel é −11% nos dois casos. É a dimensão mais estável e diretamente mensurável do mapa.")

h2("5.4 P3 — Exposição ao juro")
p("A exposição ao juro foi medida de dois modos. O primeiro olha o nível do juro real; o segundo, a direção da Selic.")
p("Nível do juro real. Para cada uma das 27 atividades calculou-se a correlação entre o crescimento anual em t e o juro real em t−k, para k de 0 a 12 meses (Figura 14). "
  "Como a escolha do melhor k dentre 13 defasagens infla a chance de achar correlação por acaso, e as séries são autocorrelacionadas, a significância foi avaliada por um teste de "
  f"permutação: o juro real é deslocado circularmente ({f(P2r['perm_n'], 0)} deslocamentos) e compara-se a correlação mais negativa observada com a distribuição do mínimo sobre as 13 defasagens. "
  f"Resultado: {P2r['n_significativas']} das {P2r['n_total']} séries têm p < 0,05; só {P2r['n_negativas']} correlações têm o sinal esperado, e a indústria geral tem correlação positiva "
  f"(+{f(P2r['geral']['r'], 2)}). O cenário de queda de 3 p.p. no juro real, aplicado aos coeficientes de uma regressão com erros de Newey-West, projeta {f(P5r['geral']['efeito'], 2)} p.p. "
  f"para a indústria geral (IC 95%: {f(P5r['geral']['ic'][0], 1)} a +{f(P5r['geral']['ic'][1], 1)}), indistinguível de zero. O nível do juro real não diferencia as divisões.")
im(EVID / "fig_P3a_juro_nivel_defasagem.png", "Figura 14 — Nível do juro: correlação entre juro real defasado e crescimento anual, por divisão (P3).")
C = R["CICLOS"]
p(f"Direção da Selic. Um mês é de ciclo de alta quando a Selic está acima da de 12 meses antes. De 2003 a 2026 houve sete ciclos de alta ({C['meses_alta_completo']} dos "
  f"{C['meses_completo']} meses analisados, sem a pandemia). Para cada divisão, compara-se o crescimento anual médio nos meses de alta com o dos meses de corte, com a mesma "
  "permutação circular para a significância. A hipótese surgiu na exploração de 2013–2026; por isso foi testada em 2003–2012, período sem nenhum mês em comum, com o critério "
  "declarado antes: confirmar-se-ia se ao menos 4 das 6 divisões significativas na exploração mantivessem sinal negativo e se o número de divisões com efeito negativo "
  "significativo superasse o esperado por acaso.")
tb(["Período", "Divisões", "Crescem menos na alta", "Negativas significativas", "Positivas significativas", "Indústria geral (p.p.)"], [
    ["2013–2026 (exploração)", str(C["exploracao"]["n_div"]), str(C["exploracao"]["n_negativas"]), str(C["exploracao"]["n_neg_sig"]), str(C["exploracao"]["n_pos_sig"]), f(C["exploracao"]["geral"]["dif"], 1)],
    ["2003–2012 (validação)", str(C["validacao"]["n_div"]), str(C["validacao"]["n_negativas"]), str(C["validacao"]["n_neg_sig"]), str(C["validacao"]["n_pos_sig"]), f(C["validacao"]["geral"]["dif"], 1)],
    ["2003–2026 (completo)", str(C["completo"]["n_div"]), str(C["completo"]["n_negativas"]), str(C["completo"]["n_neg_sig"]), str(C["completo"]["n_pos_sig"]), f(C["completo"]["geral"]["dif"], 1)],
])
im(EVID / "fig_P3b_juro_ciclos_selic.png", "Figura 15 — Direção da Selic: crescimento anual na alta menos no corte, nos dois períodos independentes (P3).")
tb(["Divisão (significativa na exploração)", "2013–2026 (p.p.)", "2003–2012 (p.p.)", "p em 2003–2012"],
   [[n, f(e, 1), f(v, 1), f(pv, 3)] for _, n, e, v, pv in C["alvos"]])
p(f"Resposta a P3. O nível do juro real não explica o crescimento de nenhuma divisão. A direção da Selic explica parte: em ciclos de alta, {C['completo']['n_negativas']} das "
  f"{C['completo']['n_div']} divisões crescem menos, e a indústria geral cresce {f(abs(C['completo']['geral']['dif']), 1)} p.p. a menos (p = {f(C['completo']['geral']['p'], 2)}). "
  f"Na validação fora da amostra, as {C['alvos_negativos_validacao']} divisões da exploração mantiveram o sinal negativo, e {C['validacao']['n_negativas']} de {C['validacao']['n_div']} apontaram na mesma direção. "
  f"Mas só {C['validacao']['n_neg_sig']} delas (Máquinas e materiais elétricos) foi significativa sozinha. Pelo critério declarado, o sinal se confirmou e a significância setorial não. "
  "H2 é parcialmente sustentada: a direção é consistente em dois períodos independentes, e os setores de duráveis e construção estão entre os mais afetados, mas o efeito de cada "
  "divisão isolada não se distingue do ruído com tão poucos ciclos. Para o mapa, a exposição ao juro de cada divisão é a diferença no período completo (2003–2026), que usa os sete ciclos.")

h2("5.5 P4 — Exposição ao câmbio")
p("Para cada atividade estimou-se por mínimos quadrados o crescimento anual contra o juro real defasado e a variação cambial de 12 meses, com erros-padrão robustos a autocorrelação e "
  "heterocedasticidade (Newey-West, 12 defasagens). A Figura 16 mostra os coeficientes com intervalos de 95%.")
im(EVID / "fig_P4_cambio_coeficientes.png", "Figura 16 — Exposição ao câmbio: coeficientes do juro real e da variação cambial por divisão (P4).")
cn = P3r["cambio_neg_sig"]
tb(["Atividade", "β câmbio (p.p. por 1% de desvalorização)", "estatística t"],
   [[f"{c} {n}", f"{b:+.2f}".replace(".", ","), f"{t:+.2f}".replace(".", ",")] for c, n, b, t in cn] +
   [["1 Indústria geral", f"{P3r['geral']['beta_cambio']:+.2f}".replace(".", ","), f"{P3r['geral']['t_cambio']:+.2f}".replace(".", ",")]])
p(f"Resposta a P4. O câmbio tem associação significativa em {P3r['n_cambio_sig']} das {P3r['n_total']} atividades, e em todas o sinal é negativo: desvalorização do real acompanha crescimento menor. "
  f"Para a indústria geral, cada 1% de desvalorização em 12 meses corresponde a {f(abs(P3r['geral']['beta_cambio']), 2)} p.p. a menos de crescimento (t = {f(P3r['geral']['t_cambio'], 1)}). "
  "Os maiores efeitos estão em Informática e eletrônicos, Veículos e Impressão, que dependem de componentes importados. Nenhuma divisão tem efeito positivo significativo: H3 não se confirma. "
  f"O poder explicativo é baixo (R² mediano {f(P3r['r2_mediano'], 2)}), e as desvalorizações de 2015 e 2020 coincidiram com recessões, o que pode atribuir ao câmbio parte do efeito do ciclo.")

h2("5.6 P5 — Síntese: mapa de risco setorial")
M = R["MAPA"]
p("Cada dimensão foi transformada em escore padronizado (z) entre as 24 divisões, com sinal tal que valor maior significa mais risco: folga (quanto abaixo de 2019), instabilidade "
  "(desvio-padrão), exposição ao juro (quanto cresce a menos na alta da Selic) e exposição ao câmbio (quanto cresce a menos por 1% de desvalorização). O índice é a média simples dos "
  "quatro escores, o critério mais transparente na ausência de uma razão para pesar uma fonte de risco acima da outra. As divisões são divididas em três faixas de oito.")
im(EVID / "fig_P5_mapa_risco.png", "Figura 17 — Mapa de risco setorial: cor = escore padronizado de cada dimensão; texto = valor na unidade original (P5).")
tb(["#", "Divisão", "Faixa", "Índice", "Folga", "Instab.", "Juro", "Câmbio"],
   [[str(int(r.ranking)), r.atividade, r.faixa, f(r.indice_risco, 2),
     f"{abs(r.folga_pp):.0f}% {'abaixo' if r.folga_pp > 0 else 'acima'}", f(r.instabilidade_pp, 1), f(r.expos_juro_pp, 1), f(r.expos_cambio_pp, 2)]
    for r in MAPA.itertuples()])
loo = M["deixa_uma_fora"]
p(f"Robustez. O ranking muda pouco com o critério. Usando a média das posições em vez da média dos escores, a correlação de postos com o índice é {f(M['spearman_indice_por_postos'], 2)}. "
  f"Retirando uma dimensão de cada vez, a correlação fica entre {f(min(v['spearman'] for v in loo.values()), 2)} e {f(max(v['spearman'] for v in loo.values()), 2)}, e das oito divisões "
  f"de risco alto continuam no topo entre {min(v['top8_mantidos'] for v in loo.values())} e {max(v['top8_mantidos'] for v in loo.values())}. As dimensões medem coisas distintas: "
  f"a maior correlação entre elas é {f(M['corr_dims_max_abs'], 2)} (instabilidade e câmbio), e a folga é quase independente das demais.")
p("Resposta a P5. As oito divisões de risco alto são Informática e eletrônicos, Veículos, Impressão, Móveis, Vestuário, Têxteis, Máquinas e materiais elétricos e Couro e calçados; "
  "as de risco baixo, Celulose e papel, Derivados de petróleo, Alimentos, Minerais não metálicos, Outros equipamentos de transporte, Químicos, Bebidas e Farmacêuticos. "
  "O mapa mostra também de onde vem o risco: em Informática e Veículos domina o câmbio, somado a alta instabilidade e exposição ao juro; em Impressão, Vestuário e Couro, a folga; "
  "em Móveis, Têxteis e Máquinas elétricas, a exposição ao juro. As três primeiras acumulam três das quatro fontes de risco: H1 confirmada. "
  "O caso de Fumo mostra por que combinar dimensões importa: é a divisão mais instável, mas está 38% acima de 2019 e pouco exposta a juro e câmbio, e fica em 16º.")
p("Discussão geral. Para a área de crédito, o mapa traduz-se em três regras de uso. (1) A faixa define o ponto de partida do limite e da provisão. (2) A dimensão dominante indica "
  "o gatilho a monitorar: início de ciclo de alta da Selic para Móveis, Têxteis, Máquinas elétricas, Veículos e Informática; desvalorização cambial para Informática, Veículos e Impressão; "
  "recuperação da demanda para Impressão, Vestuário e Couro. (3) O nível do juro real não deve ser usado como gatilho: ele não diferencia as divisões.")
p("Limitação principal. O índice mede sinais de fragilidade setorial observáveis na produção, mas não foi validado contra o risco de crédito realizado: "
  "não se verificou se as divisões de risco alto de fato têm mais inadimplência. Por isso ele deve ser lido como ferramenta de triagem e de monitoramento, "
  "não como modelo de risco de crédito, e os pesos iguais não estão calibrados. Duas ressalvas de construção se somam a essa: a exposição ao juro de cada divisão "
  "isolada é estimada com pouca precisão (o índice a atenua ao combiná-la com outras três fontes), e a folga pode refletir tanto demanda fraca quanto um setor em "
  "recuperação, que para um credor pode ser oportunidade. A validação com dados de inadimplência setorial do Banco Central é o próximo passo natural (Autoavaliação).")

# =====================================================================================================
h1("6. Ética, licenciamento e proteção de dados")
bl([
    "Licença dos dados do Banco Central (SGS). As séries 4189, 433, 13522 e 3698 estão publicadas no Portal de Dados Abertos do BCB (dadosabertos.bcb.gov.br) sob a Open Data Commons Open Database License (ODbL). A ODbL permite redistribuir e criar bases derivadas, com duas condições: atribuição da fonte e compartilhamento da base derivada sob a mesma licença. Por isso as tabelas derivadas publicadas em data/processed (os CSV de fatos, dimensões e resultados, como fato_macro.csv e tab_P5_mapa_risco.csv) são distribuídas também sob a ODbL, com atribuição ao BCB (registro no arquivo LICENSE).",
    "Licença dos dados do IBGE (SIDRA, tabela 8888). A PIM-PF é estatística oficial de divulgação pública. A reprodução é aceita com citação obrigatória da fonte, e o trabalho cita \"IBGE, Pesquisa Industrial Mensal – Produção Física, tabela 8888 (SIDRA)\" no README, no catálogo e no relatório. Não foi localizada uma licença aberta formal (do tipo CC ou ODbL) específica para a tabela, e isso fica registrado aqui. Para reutilização comercial, convém confirmar os termos diretamente com o IBGE.",
    "Versionamento dos dados brutos. Como as duas fontes permitem redistribuição com atribuição, e os arquivos são pequenos (cerca de 1,7 MB), os JSON brutos foram versionados em data/raw para garantir reprodutibilidade, inclusive no Databricks Free Edition, que não acessa a internet. O script de coleta também está publicado, e o manifesto registra URL, data e hash SHA-256 de cada arquivo.",
    "Dados pessoais (LGPD). Não se aplica: as bases são agregados nacionais mensais, sem identificadores de pessoas ou empresas.",
    "Dados corporativos. Não se aplica: nenhum dado de empresa foi utilizado.",
    "Coleta automatizada. Foram usadas apenas APIs oficiais, sem scraping, com pausa entre tentativas.",
    "Código. O código do repositório está sob a licença MIT (arquivo LICENSE).",
])

# =====================================================================================================
h1("7. Autoavaliação")
p("Objetivos atingidos. A pergunta central foi respondida: o mapa de risco classifica as 24 divisões, mostra a fonte dominante de risco de cada uma e é estável a mudanças de critério. "
  "P1, P2 e P4 foram respondidas de forma conclusiva. P3 teve resposta mista: o nível do juro real não explica a produção setorial, e a direção da Selic tem efeito de sinal consistente "
  "em dois períodos independentes, mas sem significância setor a setor. Nenhuma pergunta da primeira versão foi removida; todas viraram dimensões do mapa (Seção 1.4).")
p("Perguntas sugeridas:")
bl([
    "Quais perguntas foram respondidas e quais não? P1, P2, P4 e P5 foram respondidas. P3 foi respondida no agregado (ciclos de alta reduzem o crescimento de quase todas as divisões), mas não no detalhe: com sete ciclos de alta em 24 anos, o efeito de cada divisão isolada é estimado com pouca precisão. A versão anterior do trabalho, centrada no nível do juro, teve resposta nula; isso motivou a segunda volta do ciclo do MVP.",
    "Que limitações dos dados condicionaram os resultados? Índice sem ajuste sazonal (obrigou o uso de variação anual); poucos ciclos de juros; exclusão da pandemia; ausência de controles de crédito, renda e demanda externa; e o fato de os ciclos de alta de 2008 e de 2015 coincidirem com recessões, o que mistura o efeito do juro com o do ciclo econômico. No mapa, a limitação mais séria é a falta de validação contra o risco realizado: sem dados de inadimplência por setor, não se sabe se o ranking antecipa perdas de crédito. Os pesos iguais são uma escolha: a análise de sensibilidade mostra que o ranking muda pouco, mas não elimina a escolha.",
    "Que decisões técnicas tomaria de outra forma? Começaria pela pergunta de decisão (o mapa de risco) em vez de cinco perguntas independentes, o que teria evitado uma primeira versão sem tese. Testaria o pipeline no Databricks desde o primeiro dia: só na execução real apareceu que o Free Edition não acessa a internet. E declararia as definições dos testes, como a de ciclo de alta, antes de olhar qualquer resultado, como foi feito na validação fora da amostra.",
    "Que extensões transformariam o MVP em solução de uso contínuo? Agendamento mensal do job (Databricks Workflows) alinhado à divulgação da PIM-PF, com carga incremental; o mapa de risco republicado a cada mês como tabela Delta e painel; testes automáticos de qualidade (as verificações da Seção 5.1 como expectativas de dados); inclusão de indicadores de crédito por setor e da PIM regional; e acompanhamento da estabilidade do ranking ao longo do tempo.",
])
p("Trabalhos futuros. Identificar o efeito do juro com choques monetários (VAR estrutural ou surpresas de alta frequência), para separá-lo do ciclo econômico; validar o mapa contra inadimplência "
  "observada por setor (dados de crédito do BCB), o que permitiria calibrar os pesos em vez de fixá-los iguais; e estender o mapa a serviços e comércio.")

h1("8. Reprodutibilidade")
bl([
    "Local: python scripts/coleta.py → python scripts/etl.py → python scripts/analise.py → python scripts/gerar_catalogo.py → python scripts/gerar_relatorio.py. Dependências em requirements.txt. Semente aleatória fixa (42). O mapa de risco sai em data/processed/tab_P5_mapa_risco.csv e na tabela mapa_risco do DW.",
    "Databricks: criar uma Git folder com o repositório e executar notebooks/01, 02 e 03 em ordem. Os notebooks usam catalog workspace e schema industria_juros. O notebook 01 parte, por padrão, do bronze versionado em data/raw (o Free Edition não acessa a internet, e isso mantém os números reprodutíveis); para coletar de novo das APIs, use COLETAR_DAS_APIS = True.",
    f"Repositório: {REPO}",
    "Fontes: IBGE/SIDRA tabela 8888 (PIM-PF); BCB/SGS séries 4189, 433, 13522 e 3698.",
])


# =====================================================================================================
# Renderização
def md_render():
    out = ["# MVP — Mapa de risco setorial da indústria: pipeline de dados em nuvem com produção, juros e câmbio\n",
           f"**Universidade de Brasília — Departamento de Engenharia de Produção · {DISCIPLINA}**  \n"
           f"Aluno: {ALUNO} · Professor: André Luiz Marques Serrano\n",
           f"> Repositório: {REPO}  \n> Relatório em Word: `Relatorio_MVP_Industria_Juros_Lucas_Iwano.docx`\n",
           ]
    reproduzir = ["\n## Como reproduzir (resumo)\n",
                  "```bash\npip install -r requirements.txt\npython scripts/coleta.py && python scripts/etl.py && python scripts/analise.py\n```\n",
                  "No Databricks: crie uma *Git folder* com este repositório e execute `notebooks/01`, `02` e `03` em ordem. Detalhes na Seção 8.\n"]
    for b in B:
        if b[0] == "h1" and b[1].startswith("1."):   # o resumo vem primeiro; as instruções de execução logo depois dele
            out.extend(reproduzir)
        t = b[0]
        if t == "h1":
            out.append(f"\n## {b[1]}\n")
        elif t == "h2":
            out.append(f"\n### {b[1]}\n")
        elif t == "p":
            out.append(b[1] + "\n")
        elif t == "ul":
            out.append("\n".join(f"- {i}" for i in b[1]) + "\n")
        elif t == "table":
            head, rows = b[1], b[2]
            out.append("| " + " | ".join(head) + " |\n|" + "---|" * len(head))
            out.extend("| " + " | ".join(str(c).replace("|", "/") for c in r) + " |" for r in rows)
            out.append("")
        elif t == "img":
            rel = Path(b[1]).relative_to(ROOT).as_posix()
            out.append(f"![{b[2]}]({rel})\n\n*{b[2]}*\n")
    return "\n".join(out)


def shade(cell, cor):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear")
    sh.set(qn("w:color"), "auto")
    sh.set(qn("w:fill"), cor)
    tcPr.append(sh)


def docx_render():
    d = Document()
    sec = d.sections[0]
    sec.left_margin = sec.right_margin = Cm(2.2)
    sec.top_margin = sec.bottom_margin = Cm(2.2)
    st = d.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(11)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.line_spacing = 1.12
    for nm, sz, cor in [("Heading 1", 16, "1F4E79"), ("Heading 2", 13, "1F4E79")]:
        s = d.styles[nm]
        s.font.name = "Calibri"
        s.font.size = Pt(sz)
        s.font.bold = True
        s.font.color.rgb = RGBColor.from_string(cor)
    # capa
    for txt, sz, bold in [("UNIVERSIDADE DE BRASÍLIA", 14, True), ("Departamento de Engenharia de Produção", 12, False), (DISCIPLINA, 12, False), ("", 11, False),
                          ("MVP — MINIMUM VIABLE PRODUCT", 20, True),
                          ("Mapa de risco setorial da indústria brasileira", 16, True),
                          ("Pipeline de dados em nuvem com produção industrial, juros e câmbio para apoio à decisão de crédito", 12, False), ("", 11, False),
                          (f"Aluno: {ALUNO}", 12, False), ("Professor: André Luiz Marques Serrano", 12, False),
                          ("Novembro de 2026", 12, False), (f"Repositório: {REPO}", 11, False)]:
        par = d.add_paragraph()
        par.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = par.add_run(txt)
        r.bold = bold
        r.font.size = Pt(sz)
        if sz >= 16:
            r.font.color.rgb = RGBColor(0x1F, 0x4E, 0x79)
    d.add_page_break()
    for b in B:
        t = b[0]
        if t == "h1":
            d.add_heading(b[1], 1)
        elif t == "h2":
            d.add_heading(b[1], 2)
        elif t == "p":
            par = d.add_paragraph()
            txt = b[1]
            partes = txt.split("**")
            for i, seg in enumerate(partes):
                run = par.add_run(seg)
                run.bold = i % 2 == 1
        elif t == "ul":
            for i in b[1]:
                d.add_paragraph(i, style="List Bullet")
        elif t == "table":
            head, rows = b[1], b[2]
            tab = d.add_table(rows=1, cols=len(head))
            tab.style = "Table Grid"
            tab.alignment = WD_TABLE_ALIGNMENT.CENTER
            for i, hd in enumerate(head):
                c = tab.rows[0].cells[i]
                c.text = ""
                run = c.paragraphs[0].add_run(hd)
                run.bold = True
                run.font.size = Pt(9)
                run.font.color.rgb = RGBColor(255, 255, 255)
                shade(c, "1F4E79")
            for r in rows:
                cells = tab.add_row().cells
                for i, v in enumerate(r):
                    cells[i].text = ""
                    run = cells[i].paragraphs[0].add_run(str(v))
                    run.font.size = Pt(8.5)
            pesos = [min(max(len(str(x)) for x in [head[i]] + [r[i] for r in rows]), 38) + 12 for i in range(len(head))]
            tab.autofit = False
            for i, w in enumerate(pesos):
                for row in tab.rows:
                    row.cells[i].width = Cm(16.6 * w / sum(pesos))
            d.add_paragraph()
        elif t == "img":
            d.add_picture(str(b[1]), width=Cm(15.5))
            d.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
            cap = d.add_paragraph()
            cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
            rr = cap.add_run(b[2])
            rr.italic = True
            rr.font.size = Pt(9)
    d.save(DOCX_OUT)


(ROOT / "README.md").write_text(md_render(), encoding="utf-8")
docx_render()
print("README.md e", DOCX_OUT.name, "gerados;", len(B), "blocos")
