import pandas as pd
import plotly.graph_objects as go

AGE_ORDER = [
    "0 a 4 anos","5 a 9 anos","10 a 14 anos","15 a 19 anos",
    "20 a 24 anos","25 a 29 anos","30 a 39 anos","40 a 49 anos",
    "50 a 59 anos","60 a 69 anos","70 anos ou mais"
]

def make_age_pyramid(df: pd.DataFrame, title: str = "Pirâmide etária") -> go.Figure:
    df = df.copy()
    df["idade_grupo"] = pd.Categorical(df["idade_grupo"], categories=AGE_ORDER, ordered=True)
    males = df[df["sexo"].str.lower().str.startswith("m")].copy()
    females = df[df["sexo"].str.lower().str.startswith("f")].copy()
    males["valor"] = -pd.to_numeric(males["valor"], errors="coerce")
    females["valor"] = pd.to_numeric(females["valor"], errors="coerce")
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
    fig.update_xaxes(tickformat=",", title=None)
    return fig
