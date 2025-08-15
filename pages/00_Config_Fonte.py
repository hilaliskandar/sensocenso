import streamlit as st
import os
from pathlib import Path

definir_fonte = st.radio(
    "Fonte dos dados:",
    ["Parquet local", "MotherDuck (nuvem)"]
)

if definir_fonte == "Parquet local":
    parquet_path = st.text_input(
        "Caminho do Parquet",
        st.session_state.get("parquet_path", r"D:\repo\saida_parquet\base_integrada_final.parquet"),
        key="parquet_path"
    )
    st.session_state["fonte_dados"] = "parquet"
    st.success(f"Fonte definida: Parquet local ({parquet_path})")
else:
    db_name = st.text_input("Nome do banco MotherDuck", st.session_state.get("md_db", "sensocenso"), key="md_db")
    table_name = st.text_input("Nome da tabela MotherDuck", st.session_state.get("md_table", "censo2022"), key="md_table")
    st.session_state["fonte_dados"] = "motherduck"
    st.success(f"Fonte definida: MotherDuck (db: {db_name}, tabela: {table_name})")

if st.button("Salvar e testar"):
    try:
        if st.session_state["fonte_dados"] == "parquet":
            path = Path(st.session_state["parquet_path"])
            if not path.exists():
                st.error(f"Arquivo não encontrado: {path}")
            else:
                import pandas as pd
                df = pd.read_parquet(path)
                st.write(df.head())
                st.success(f"Amostra carregada do Parquet ({len(df):,} linhas)")
        else:
            import duckdb
            token = os.environ.get("motherduck_token")
            if not token:
                st.error("Token MotherDuck não encontrado. Configure a variável de ambiente motherduck_token.")
            else:
                con = duckdb.connect(f"md:{st.session_state['md_db']}")
                query = f"SELECT * FROM {st.session_state['md_table']} LIMIT 10"
                df = con.execute(query).fetchdf()
                con.close()
                st.write(df.head())
                st.success(f"Amostra carregada do MotherDuck ({len(df):,} linhas)")
    except Exception as e:
        st.error(f"Erro ao testar fonte: {e}")
