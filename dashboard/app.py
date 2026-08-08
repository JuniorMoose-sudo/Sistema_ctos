"""
Dashboard do gestor — visão consolidada.

Lê da API Django (não direto do banco) para reaproveitar as mesmas regras de
negócio do backend:

- /api/ctos/          -> visão consolidada: cada CTO com status_atual (espelho
                         da última ocorrência) + data da última ocorrência.
                         Base para KPIs e mapa colorido por situação.
- /api/ocorrencias/   -> histórico (ranking, evolução, exportação CSV).

Rodar: streamlit run dashboard/app.py
"""
import os
from datetime import date
from pathlib import Path

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv

# Carrega o .env da raiz do projeto (API_BASE_URL, API_TOKEN, etc.)
_PROJETO = Path(__file__).resolve().parent.parent
load_dotenv(_PROJETO / ".env")

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api")
env_token = os.environ.get("API_TOKEN", "")

# ---- Cores por status (mesmo esquema visual do Google Earth/KMZ) ----
CORES_STATUS = {
    "normal": "#22c55e",          # verde
    "proxima_lotacao": "#f59e0b", # amarelo/âmbar
    "lotada": "#ef4444",          # vermelho
    "danificada": "#a855f7",      # roxo
}
LABEL_STATUS = {
    "normal": "Normal",
    "proxima_lotacao": "Próxima da lotação",
    "lotada": "Lotada",
    "danificada": "Danificada",
}

st.set_page_config(page_title="CTOs Lotadas — Campina Grande", layout="wide")
st.title("📡 Monitoramento de CTOs — Campina Grande")
st.caption("Visão consolidada: status de cada CTO reflete a **última ocorrência registrada**.")

API_TOKEN = st.sidebar.text_input("API Token (Gestor)", value=env_token, type="password")

if not API_TOKEN:
    st.sidebar.error("Configure o API_TOKEN (no .env ou na URL) para carregar os dados.")
    st.stop()


def _headers(token: str):
    return {"Authorization": f"Token {token}"} if token else {}


@st.cache_data(ttl=60)
def carregar_ctos(token: str) -> pd.DataFrame:
    """Visão consolidada de todas as CTOs com status atual."""
    resp = requests.get(f"{API_BASE_URL}/ctos/", headers=_headers(token), timeout=60)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


@st.cache_data(ttl=60)
def carregar_ocorrencias(token: str, filtros: dict) -> pd.DataFrame:
    """Histórico de ocorrências, com os filtros ativos."""
    resp = requests.get(
        f"{API_BASE_URL}/ocorrencias/", params=filtros, headers=_headers(token), timeout=60
    )
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


@st.cache_data(ttl=60)
def montar_fig_mapa(df: pd.DataFrame, zoom: float, center: dict):
    """Constrói o scatter_map. Cacheado para não recriar 5.744 pontos
    a cada interação com qualquer widget (principal travamento do dashboard)."""
    hover = {
        "nome": True,
        "bairro": True,
        "cidade": True,
        "status_atual": True,
        "portas_livres_atual": True,
        "latitude": False,
        "longitude": False,
        "ultima_ocorrencia": True,
    }
    fig = px.scatter_map(
        df,
        lat="latitude",
        lon="longitude",
        color="status_atual",
        color_discrete_map=CORES_STATUS,
        hover_name="nome",
        hover_data=hover,
        zoom=zoom,
        center=center,
        height=650,
    )
    fig.update_layout(
        legend_title_text="Situação",
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )
    return fig


# ===================== CARGA DOS DADOS =====================
try:
    df_ctos = carregar_ctos(API_TOKEN)
except requests.RequestException as e:
    st.error(f"Não foi possível carregar os dados da API: {e}")
    st.stop()

df_ctos["latitude"] = df_ctos["latitude"].astype(float)
df_ctos["longitude"] = df_ctos["longitude"].astype(float)
df_ctos["bairro"] = df_ctos["bairro"].fillna("Não informado")
df_ctos["cidade"] = df_ctos["cidade"].fillna("Campina Grande")
df_ctos["localidade"] = df_ctos["bairro"].where(df_ctos["bairro"] != "Não informado", df_ctos["cidade"])

# ===================== FILTROS (sidebar) =====================
st.sidebar.header("Filtros")

cidades_opcoes = sorted(df_ctos["cidade"].unique().tolist())
cidades_sel = st.sidebar.multiselect("Cidade", cidades_opcoes, default=[])

mask_cidade = pd.Series(True, index=df_ctos.index)
if cidades_sel:
    mask_cidade &= df_ctos["cidade"].isin(cidades_sel)
df_ctos_por_cidade = df_ctos[mask_cidade]

bairros_opcoes = sorted(df_ctos_por_cidade["bairro"].unique().tolist())
bairros_sel = st.sidebar.multiselect("Bairro", bairros_opcoes, default=[])

status_opcoes = list(LABEL_STATUS.values())
status_sel_labels = st.sidebar.multiselect("Situação", status_opcoes, default=[])
status_sel = {v: k for k, v in LABEL_STATUS.items()}.get(status_sel_labels[0], "") if len(status_sel_labels) == 1 else ""
if len(status_sel_labels) > 1:
    status_sel = [v for k, v in LABEL_STATUS.items() if k in status_sel_labels]

data_inicio = st.sidebar.date_input("Data início", value=None)
data_fim = st.sidebar.date_input("Data fim", value=None)
st.sidebar.caption("Filtros de data valem para o histórico (evolução, ranking e CSV).")

# ---- Aplica filtros na visão consolidada de CTOs ----
mask_ctos = pd.Series(True, index=df_ctos.index)
if cidades_sel:
    mask_ctos &= df_ctos["cidade"].isin(cidades_sel)
if bairros_sel:
    mask_ctos &= df_ctos["bairro"].isin(bairros_sel)
if status_sel:
    if isinstance(status_sel, list):
        mask_ctos &= df_ctos["status_atual"].isin(status_sel)
    else:
        mask_ctos &= df_ctos["status_atual"] == status_sel

df_ctos_filtro = df_ctos[mask_ctos]

# ===================== KPIs (status atual, consolidado) =====================
df_lotadas = df_ctos_filtro[df_ctos_filtro["status_atual"] == "lotada"]
df_quase = df_ctos_filtro[df_ctos_filtro["status_atual"] == "proxima_lotacao"]
df_danificadas = df_ctos_filtro[df_ctos_filtro["status_atual"] == "danificada"]

# "Atualizadas hoje": última ocorrência registrada hoje (fuso America/Recife)
hoje = date.today()
if "ultima_ocorrencia" in df_ctos_filtro.columns:
    dt_ultima = pd.to_datetime(df_ctos_filtro["ultima_ocorrencia"], errors="coerce", utc=True)
    atualizadas_hoje = dt_ultima.dt.tz_convert("America/Recife").dt.date.eq(hoje).sum()
else:
    atualizadas_hoje = 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total de CTOs", f"{len(df_ctos_filtro):,}".replace(",", "."))
col2.metric("🔴 Lotadas", f"{len(df_lotadas):,}".replace(",", "."))
col3.metric("🟡 Quase lotadas", f"{len(df_quase):,}".replace(",", "."))
col4.metric("🟣 Danificadas", f"{len(df_danificadas):,}".replace(",", "."))
col5.metric("Atualizadas hoje", f"{atualizadas_hoje}")

st.divider()

# ===================== MAPA CONSOLIDADO =====================
st.subheader("🗺️ Mapa consolidado por situação")

# ---- Busca por coordenadas (centro/zoom do mapa) ----
CAMPINA_GRANDE = {"lat": -7.2306, "lon": -35.8811}
if "map_center" not in st.session_state:
    st.session_state["map_center"] = CAMPINA_GRANDE
    st.session_state["map_zoom"] = 11

with st.expander("🔍 Ir para uma localização por coordenadas"):
    st.caption("Informe as coordenadas (ex.: no Google Maps / Google Earth, clique com o botão direito).")
    col_lat, col_lon = st.columns(2)
    lat_input = col_lat.number_input("Latitude", value=None, format="%.6f", step=0.000001, key="coord_lat")
    lon_input = col_lon.number_input("Longitude", value=None, format="%.6f", step=0.000001, key="coord_lon")

    col_btn, col_reset = st.columns(2)
    if col_btn.button("📍 Ir para coordenada", width="stretch", type="primary"):
        if lat_input is None or lon_input is None:
            st.warning("Informe latitude e longitude para navegar.")
        else:
            st.session_state["map_center"] = {"lat": float(lat_input), "lon": float(lon_input)}
            st.session_state["map_zoom"] = 17
            st.session_state.pop("coord_lat", None)
            st.session_state.pop("coord_lon", None)
    if col_reset.button("↩️ Voltar para Campina Grande", width="stretch"):
        st.session_state["map_center"] = CAMPINA_GRANDE
        st.session_state["map_zoom"] = 11

if df_ctos_filtro.empty:
    st.info("Nenhuma CTO encontrada para os filtros selecionados.")
else:
    fig_mapa = montar_fig_mapa(
        df_ctos_filtro,
        st.session_state["map_zoom"],
        st.session_state["map_center"],
    )
    st.plotly_chart(fig_mapa, width="stretch")

    st.caption(
        "Cada ponto é uma CTO. A cor representa a situação atual (última ocorrência). "
        "Passe o mouse para ver nome, bairro, portas livres e data da última atualização."
    )

st.divider()

# ===================== RANKING POR BAIRRO =====================
st.subheader("🏙️ Ranking de lotadas por bairro")

ranking = (
    df_ctos_filtro[df_ctos_filtro["status_atual"] == "lotada"]
    .groupby("localidade")
    .size()
    .sort_values(ascending=False)
    .reset_index(name="qtd_lotadas")
)
if ranking.empty:
    st.info("Nenhuma CTO lotada no filtro atual.")
else:
    top = ranking.head(10)
    fig_rank = px.bar(
        top,
        x="qtd_lotadas",
        y="localidade",
        orientation="h",
        color_discrete_sequence=["#ef4444"],
        text="qtd_lotadas",
    )
    fig_rank.update_layout(
        yaxis={"categoryorder": "total ascending"},
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )
    st.plotly_chart(fig_rank, width="stretch")

st.divider()

# ===================== HISTÓRICO (ocorrências) =====================
st.subheader("📈 Evolução das ocorrências (histórico)")

filtros_ocorr = {
    k: v
    for k, v in {
        "bairro": bairros_sel[0] if len(bairros_sel) == 1 else None,
        "situacao": status_sel if isinstance(status_sel, str) and status_sel else None,
        "data_inicio": data_inicio.isoformat() if data_inicio else None,
        "data_fim": data_fim.isoformat() if data_fim else None,
    }.items()
    if v
}

try:
    df_ocorr = carregar_ocorrencias(API_TOKEN, filtros_ocorr)
except requests.RequestException as e:
    st.warning(f"Não foi possível carregar o histórico: {e}")
    df_ocorr = pd.DataFrame()

if not df_ocorr.empty:
    df_ocorr["criado_em"] = pd.to_datetime(df_ocorr["criado_em"], errors="coerce", utc=True)
    df_ocorr["periodo"] = (
        df_ocorr["criado_em"]
        .dt.tz_convert("America/Recife")
        .dt.tz_localize(None)
        .dt.to_period("M")
        .astype(str)
    )

    evolucao = df_ocorr.groupby(["periodo", "situacao"]).size().reset_index(name="qtd")
    if not evolucao.empty:
        fig_evol = px.line(
            evolucao,
            x="periodo",
            y="qtd",
            color="situacao",
            color_discrete_map=CORES_STATUS,
            markers=True,
        )
        fig_evol.update_layout(
            legend_title_text="Situação",
            xaxis_title="",
            yaxis_title="Quantidade",
            margin={"r": 0, "t": 0, "l": 0, "b": 0},
        )
        st.plotly_chart(fig_evol, width="stretch")

    st.subheader("Ocorrências")
    cols_tabela = [c for c in ["nome_cto", "bairro", "situacao", "motivo", "portas_usadas", "portas_livres", "tecnico_username", "observacao", "criado_em"] if c in df_ocorr.columns]
    st.dataframe(df_ocorr[cols_tabela], width="stretch")

    # ===================== EXPORTAÇÃO CSV =====================
    st.subheader("Exportar CSV")
    colunas_exportacao = [
        "nome_cto", "bairro", "cidade", "latitude", "longitude", "situacao", "motivo",
        "portas_usadas", "portas_livres", "tecnico", "data_hora_registro", "observacao",
        "latitude_registro", "longitude_registro",
    ]
    df_export = df_ocorr[["nome_cto", "bairro", "situacao", "motivo", "portas_usadas", "portas_livres", "tecnico_username", "observacao", "criado_em", "latitude_registro", "longitude_registro"]].copy()
    # Junta lat/lon e cidade da CTO (obrigatório na exportação)
    lat_lon = df_ctos[["nome", "latitude", "longitude", "cidade"]].rename(columns={"nome": "nome_cto"})
    df_export = df_export.merge(lat_lon, on="nome_cto", how="left")
    df_export = df_export.rename(
        columns={
            "tecnico_username": "tecnico",
            "criado_em": "data_hora_registro",
        }
    )
    df_export = df_export[[c for c in colunas_exportacao if c in df_export.columns]]
    csv_bytes = df_export.to_csv(index=False, sep=";").encode("utf-8-sig")

    st.download_button(
        "⬇️ Baixar CSV (respeitando filtros ativos)",
        data=csv_bytes,
        file_name="ctos_lotadas_export.csv",
        mime="text/csv",
        help="CSV com separador ';' e BOM UTF-8 para abrir direto no Excel PT-BR.",
    )
else:
    st.info("Nenhuma ocorrência no histórico para os filtros selecionados.")
