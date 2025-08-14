import streamlit as st

# === Bootstrapping de imports (robusto) ===
import sys
from pathlib import Path as _Path

def _find_and_add_src(anchor: _Path, levels: int = 6):
    # Adiciona a pasta 'src' mais próxima ao sys.path, subindo até 'levels' níveis.
    for i in range(levels + 1):
        base = anchor if i == 0 else anchor.parents[i-1]
        cand = base / "src"
        if cand.exists() and (cand / "censo_app").exists():
            if str(cand) not in sys.path:
                sys.path.insert(0, str(cand))
            if str(base) not in sys.path:
                sys.path.insert(0, str(base))
            return cand
    return None

_THIS = _Path(__file__).resolve()
_src = _find_and_add_src(_THIS.parent, levels=6)
if _src is None:
    _src = _find_and_add_src(_Path.cwd(), levels=6)

import yaml

try:
    from censo_app.chroma_qa import ChromaQA
except ModuleNotFoundError:
    try:
        from src.censo_app.chroma_qa import ChromaQA
    except ModuleNotFoundError as e:
        st.error("Não foi possível importar 'censo_app.chroma_qa' nem 'src.censo_app.chroma_qa'.")
        import sys
        from pathlib import Path
        st.write("cwd:", Path.cwd())
        st.write("file:", Path(__file__).resolve())
        st.write("sys.path (top 10):", sys.path[:10])
        raise

st.title("🔎 Busca & QA (Chroma)")
st.caption("Compatível com o indexador externo. Use o mesmo modelo, coleção e diretório persistente.")

use_cfg = st.checkbox("Ler parâmetros de um config.yaml", value=True)
persist_dir = st.text_input("Chroma persist_directory", r"F:\ale_2_0\Ale_2_0_RAG\db")
cfg_guess = st.text_input("Caminho do config.yaml", r"F:\ale_2_0\Ale_2_0_RAG\config.yaml")
collection = st.text_input("Coleção (collection)", "geral")
model_name = st.text_input("Modelo de embeddings (SentenceTransformers)", "intfloat/multilingual-e5-large")
top_k = st.slider("Top K", 1, 50, 5)

if use_cfg and cfg_guess:
    try:
        cfg = yaml.safe_load(open(cfg_guess, "r", encoding="utf-8").read()) or {}
        persist_dir = cfg.get("chroma", {}).get("persist_directory", persist_dir)
        collection = cfg.get("collections", {}).get("default", collection)
        model_name = cfg.get("embeddings", {}).get("model_name", model_name)
        st.success(f"YAML carregado de: {cfg_guess}")
    except Exception as e:
        st.warning(f"Falha ao ler YAML: {e}")

persist_dir = persist_dir.replace("\\", "/")
qa = ChromaQA(persist_directory=persist_dir, collection=collection, model_name=model_name)

q = st.text_input("Pergunte algo (em PT):", "O que é índice de envelhecimento?")
if st.button("Pesquisar"):
    with st.spinner("Consultando Chroma..."):
        try:
            hits = qa.search(q, top_k=top_k)
            if not hits:
                st.info("Nenhum resultado.")
            else:
                for h in hits:
                    st.markdown(f"**score:** {h['distance']:.4f} — **fonte:** `{h['source']}`")
                    st.write(h["content"][:1000])
                    st.divider()
        except Exception as e:
            st.error(f"Falha na consulta: {e}")
