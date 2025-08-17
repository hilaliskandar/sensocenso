import re
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

AGE_ORDER_10 = [
    "0 a 4 anos","5 a 9 anos","10 a 14 anos","15 a 19 anos",
    "20 a 24 anos","25 a 29 anos","30 a 39 anos","40 a 49 anos",
    "50 a 59 anos","60 a 69 anos","70 anos ou mais"
]

AGE_ORDER_5 = [
    "0 a 4 anos","5 a 9 anos","10 a 14 anos","15 a 19 anos",
    "20 a 24 anos","25 a 29 anos","30 a 34 anos","35 a 39 anos",
    "40 a 44 anos","45 a 49 anos","50 a 54 anos","55 a 59 anos",
    "60 a 64 anos","65 a 69 anos","70 anos ou mais"
]

def _derive_age_order(labels: pd.Series) -> list[str]:
    vals = [str(x) for x in labels.dropna().unique().tolist()]
    if all(v in AGE_ORDER_5 for v in vals):
        return AGE_ORDER_5
    if all(v in AGE_ORDER_10 for v in vals):
        return AGE_ORDER_10
    # Fallback: sort by lower bound numeric
    def key(lbl: str) -> int:
        s = str(lbl)
        m = re.search(r"(\d+)\s*a\s*(\d+)", s)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d+)\s*anos?\s*ou\s*mais", s, re.IGNORECASE)
        if m:
            return int(m.group(1))
        m = re.search(r"(\d+)", s)
        return int(m.group(1)) if m else 99999
    # Keep original labels order based on computed key, ensuring stability
    return sorted(vals, key=key)

def make_age_pyramid(df: pd.DataFrame, title: str = "Pirâmide etária") -> go.Figure:
    df = df.copy()
    order = _derive_age_order(df["idade_grupo"]) if "idade_grupo" in df.columns else AGE_ORDER_5
    df["idade_grupo"] = pd.Categorical(df["idade_grupo"], categories=order, ordered=True)
    males = df[df["sexo"].astype(str).str.lower().str.startswith("m")].copy()
    females = df[df["sexo"].astype(str).str.lower().str.startswith("f")].copy()
    males["valor"] = -pd.to_numeric(males["valor"], errors="coerce").fillna(0)
    females["valor"] = pd.to_numeric(females["valor"], errors="coerce").fillna(0)
    males = males.sort_values("idade_grupo")
    females = females.sort_values("idade_grupo")

    fig = go.Figure()
    fig.add_bar(y=males["idade_grupo"], x=males["valor"], name="Masculino", orientation="h")
    fig.add_bar(y=females["idade_grupo"], x=females["valor"], name="Feminino", orientation="h")
    fig.update_layout(
        barmode="overlay",
        title=title,
        xaxis_title="População",
        yaxis_title="Grupo de idade",
        bargap=0.1,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_yaxes(categoryorder='array', categoryarray=order)
    fig.update_xaxes(tickformat=",", title=None)
    return fig

# Alias em PT-BR (API pública preferencial)
def construir_piramide_etaria(df: pd.DataFrame, titulo: str = "Pirâmide etária") -> go.Figure:
    return make_age_pyramid(df, title=titulo)

# --- Categóricos ---
def make_pie_chart(df, categoria_col: str = "categoria", valor_col: str = "valor", titulo: str | None = None):
    fig = px.pie(df, names=categoria_col, values=valor_col, hole=0.0)
    if titulo:
        fig.update_layout(title_text=titulo, title_x=0.5)
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    return fig

def make_bar_chart(df, categoria_col: str = "categoria", valor_col: str = "valor", titulo: str | None = None):
    order = df.sort_values(valor_col, ascending=True)[categoria_col].tolist()
    fig = px.bar(df, x=valor_col, y=categoria_col, orientation='h', category_orders={categoria_col: order})
    if titulo:
        fig.update_layout(title_text=titulo, title_x=0.5)
    fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
    return fig

# Aliases PT-BR
def construir_grafico_pizza(df, categoria_col: str = "categoria", valor_col: str = "valor", titulo: str | None = None):
    return make_pie_chart(df, categoria_col, valor_col, titulo)

def construir_grafico_barra(df, categoria_col: str = "categoria", valor_col: str = "valor", titulo: str | None = None):
    return make_bar_chart(df, categoria_col, valor_col, titulo)
