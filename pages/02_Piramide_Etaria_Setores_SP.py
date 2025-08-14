import sys
from pathlib import Path as _P
SRC = _P(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import streamlit as st
import pandas as pd
import re

from censo_app.transform import (
    load_sp_age_sex_enriched, wide_to_long_pyramid, aggregate_pyramid,
    merge_rm_au_from_excel, VAR_ALIAS, SITUACAO_MAP, TIPO_MAP
)
from censo_app.viz import make_age_pyramid

st.title("🚀 Pirâmides Etárias — Setores Censitários (SP) + Variáveis & RM/AU (v6)")

st.markdown(
    "Carrega a base **Parquet** de setores (SP), inclui variáveis **V0001..V0007** (com *aliases* e tipos), "
    "traz **Situação/Tipo de setor** (com decodificação) e permite juntar **RM/Aglomeração** via Excel."
)

def norm_path(s: str) -> str:
    s = (s or "").strip().strip('"').strip("'")
    return s.replace("\\", "/")

parquet_path = st.text_input("Caminho do Parquet", r"D:\\repo\\saida_parquet\\base_integrada_final.parquet")
xlsx_path = st.text_input("Excel de RM/AU (opcional)", r"D:\\repo\\insumos\\Composicao_RM_2024.xlsx")
parquet_path = norm_path(parquet_path)
xlsx_path = norm_path(xlsx_path)

col1, col2, col3 = st.columns([1,1,1])
limit = col1.number_input("Limite (amostra)", min_value=0, value=0, help="0 = tudo")
do_merge = col2.checkbox("Juntar RM/AU do Excel", value=True)
go = col3.button("Carregar & Preparar")
st.divider()

with st.expander("🔎 Diagnóstico de caminhos"):
    p_parquet = _P(parquet_path)
    p_xlsx = _P(xlsx_path)
    st.write("Parquet:", p_parquet, "| exists:", p_parquet.exists())
    st.write("Excel:", p_xlsx, "| exists:", p_xlsx.exists())
    st.write("Parquet (resolve):", p_parquet.resolve() if p_parquet.exists() else "(inexistente)")
    st.write("Excel (resolve):", p_xlsx.resolve() if p_xlsx.exists() else "(inexistente)")

if go:
    p_parquet = _P(parquet_path)
    if not p_parquet.exists():
        st.error(f"Parquet **não encontrado**: {p_parquet}. Ajuste o caminho acima.")
        st.stop()

    with st.spinner("Lendo Parquet (apenas SP) e preparando..."):
        try:
            df_wide = load_sp_age_sex_enriched(str(p_parquet), limit=int(limit) if limit else None, verbose=False)
            st.success(f"{len(df_wide):,} setores carregados (SP)." )
        except Exception as e:
            st.error(f"Falha na leitura do Parquet: {e}")
            st.stop()

        if do_merge:
            p_xlsx = _P(xlsx_path)
            if not p_xlsx.exists():
                st.warning(f"Excel **não encontrado**: {p_xlsx}. Prosseguindo sem RM/AU.")
            else:
                try:
                    df_wide = merge_rm_au_from_excel(df_wide, str(p_xlsx))
                    st.info("Merge com RM/AU aplicado.")
                except Exception as e:
                    st.warning(f"Não consegui mesclar RM/AU: {e}")

        df_long = wide_to_long_pyramid(df_wide)

    st.subheader("Filtros")
    c1, c2, _ = st.columns([1,1,1])
    sit_opts = sorted(SITUACAO_MAP.items())
    tipo_opts = sorted(TIPO_MAP.items())
    sel_sit = c1.multiselect("Situação (CD_SITUACAO)", [k for k,_ in sit_opts], placeholder="Todos")
    sel_tip = c2.multiselect("Tipo (CD_TIPO)", [k for k,_ in tipo_opts], placeholder="Todos")

    if sel_sit and "CD_SITUACAO" in df_long.columns:
        df_long = df_long[df_long["CD_SITUACAO"].isin(sel_sit)]
    if sel_tip and "CD_TIPO" in df_long.columns:
        df_long = df_long[df_long["CD_TIPO"].isin(sel_tip)]

    # Garante que nomes decodificados existem para exibição
    if "SITUACAO" in df_long.columns and df_long["SITUACAO"].isna().all() and "CD_SITUACAO" in df_long.columns:
        from censo_app.transform import SITUACAO_MAP as _SM
        df_long["SITUACAO"] = df_long["CD_SITUACAO"].map(_SM)
    if "TP_SETOR" in df_long.columns and df_long["TP_SETOR"].isna().all() and "CD_TIPO" in df_long.columns:
        from censo_app.transform import TIPO_MAP as _TM
        df_long["TP_SETOR"] = df_long["CD_TIPO"].map(_TM)

    st.subheader("Visualização")
    modo = st.radio("Nível:", ["setor","municipio","estado","rm","au"], horizontal=True)

    key = None
    if modo == "setor" and "CD_SETOR" in df_long.columns:
        # Seleção do município com rótulo CD_MUN — NM_MUN
        if all(c in df_long.columns for c in ["CD_MUN","NM_MUN"]):
            mun_df = df_long[["CD_MUN","NM_MUN"]].dropna().drop_duplicates()
            mun_df = mun_df.sort_values(["NM_MUN","CD_MUN"])  # ordena por nome
            labels = [f"{r.CD_MUN} — {r.NM_MUN}" for r in mun_df.itertuples(index=False)]
            label_to_code = dict(zip(labels, mun_df["CD_MUN"].tolist()))
            sel_label = st.selectbox("Município", ["<todos>"] + labels)
            sel_mun = None if sel_label == "<todos>" else label_to_code[sel_label]
        else:
            # fallback: só o código
            munis = sorted(df_long["CD_MUN"].dropna().unique().tolist()) if "CD_MUN" in df_long.columns else []
            sel_mun = st.selectbox("Município (CD_MUN)", [None] + munis)

        df_view = df_long if (sel_mun is None) else df_long[df_long["CD_MUN"] == sel_mun]

        # Escolher se quer totalizar o município ou visualizar por setor
        modo_setor = st.radio("Exibir:", ["Total do município","Por setor"], horizontal=True)

        if modo_setor == "Por setor":
            # Lista todos os setores do município selecionado
            with st.expander("Ver lista de setores do município selecionado", expanded=False):
                if sel_mun is None:
                    st.info("Selecione um município para listar seus setores.")
                else:
                    cols_show = [c for c in ["CD_SETOR","SITUACAO","CD_SITUACAO","TP_SETOR","CD_TIPO"] if c in df_view.columns]
                    st.dataframe(df_view[cols_show].drop_duplicates().sort_values("CD_SETOR"))

            setores = sorted(df_view["CD_SETOR"].dropna().unique().tolist())
            key = st.selectbox("Selecione o setor (CD_SETOR)", setores) if setores else None
            if key is None:
                st.warning("Nenhum setor disponível para o filtro atual.")
                st.stop()
            df_plot = aggregate_pyramid(df_view, "setor", key=key)

        else:  # Total do município
            if sel_mun is None:
                st.warning("Escolha um município para totalizar.")
                st.stop()
            df_plot = aggregate_pyramid(df_view, "municipio", key=sel_mun)

    elif modo == "municipio" and "CD_MUN" in df_long.columns:
        if all(c in df_long.columns for c in ["CD_MUN","NM_MUN"]):
            mun_df = df_long[["CD_MUN","NM_MUN"]].dropna().drop_duplicates().sort_values(["NM_MUN","CD_MUN"])
            labels = [f"{r.CD_MUN} — {r.NM_MUN}" for r in mun_df.itertuples(index=False)]
            label_to_code = dict(zip(labels, mun_df["CD_MUN"].tolist()))
            sel_label = st.selectbox("Município", labels)
            key = label_to_code[sel_label]
        else:
            munis = sorted(df_long["CD_MUN"].dropna().unique().tolist())
            key = st.selectbox("CD_MUN", munis) if munis else None
        df_plot = aggregate_pyramid(df_long, "municipio", key=key) if key else pd.DataFrame()

    elif modo == "rm" and "CD_RM" in df_long.columns:
        rms = sorted(df_long["CD_RM"].dropna().unique().tolist())
        key = st.selectbox("CD_RM", ["<todas>"] + rms)
        key = None if key == "<todas>" else key
        df_plot = aggregate_pyramid(df_long, "rm", key=key)

    elif modo == "au" and "CD_AU" in df_long.columns:
        aus = sorted(df_long["CD_AU"].dropna().unique().tolist())
        key = st.selectbox("CD_AU", ["<todas>"] + aus)
        key = None if key == "<todas>" else key
        df_plot = aggregate_pyramid(df_long, "au", key=key)

    else:
        df_plot = aggregate_pyramid(df_long, "estado")  # estado

    if df_plot.empty:
        st.warning("Nenhum dado para plotar com os filtros atuais.")
        st.stop()

    st.dataframe(df_plot.head(50))
    fig = make_age_pyramid(df_plot, title=f"Pirâmide etária — {modo.upper()}" + (f" — {key}" if key else ""))
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Exportar dataset LONG (com variáveis e geo)")
    colx, coly = st.columns([1,1])
    if colx.button("Salvar → Parquet"):
        out_path = _P("data/piramide_setorial_sp_enriched.parquet")
        df_long.to_parquet(out_path, index=False)
        st.success(f"Salvo em {out_path.resolve()}")
    if coly.button("Salvar → CSV"):
        out_path = _P("data/piramide_setorial_sp_enriched.csv")
        df_long.to_csv(out_path, index=False)
        st.success(f"Salvo em {out_path.resolve()}")
