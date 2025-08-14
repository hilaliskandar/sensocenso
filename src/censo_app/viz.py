
import pandas as pd
import plotly.graph_objects as go

def make_age_pyramid(df: pd.DataFrame, title: str = "Pirâmide etária") -> go.Figure:
    males = df[df["sexo"].str.lower().str.startswith("m")].copy()
    females = df[df["sexo"].str.lower().str.startswith("f")].copy()
    def age_sort_key(s: str) -> int:
        import re
        m = re.search(r"(\d+)", str(s))
        return int(m.group(1)) if m else 999
    order = sorted(df["idade_grupo"].unique(), key=age_sort_key)
    males["valor"] = -pd.to_numeric(males["valor"], errors="coerce")
    females["valor"] = pd.to_numeric(females["valor"], errors="coerce")
    males = males.set_index("idade_grupo").reindex(order).reset_index()
    females = females.set_index("idade_grupo").reindex(order).reset_index()
    fig = go.Figure()
    fig.add_bar(y=males["idade_grupo"], x=males["valor"], name="Masculino", orientation="h")
    fig.add_bar(y=females["idade_grupo"], x=females["valor"], name="Feminino", orientation="h")
    fig.update_layout(barmode="overlay", title=title, xaxis_title="População", yaxis_title="Grupo de idade", bargap=0.1,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
    fig.update_xaxes(tickformat=",", title=None)
    return fig
