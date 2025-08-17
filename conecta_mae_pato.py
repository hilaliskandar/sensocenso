import os, pathlib, sys
import duckdb

# --- CONFIG --- #
DBNAME   = os.getenv("MD_DATABASE", "sensocenso")
PARQUET  = r"D:\repo\saida_parquet\base_integrada_final.parquet"  # ajuste se preciso
TOKEN    = os.getenv("MOTHERDUCK_TOKEN")  # defina no PowerShell: $env:MOTHERDUCK_TOKEN="mdp_..."
TABLE    = "censo2022"
UF_CODE  = "35"  # SP
# ------------- #

if not TOKEN:
    sys.exit("Defina MOTHERDUCK_TOKEN no ambiente (PowerShell) antes de executar.")

# o DuckDB/MotherDuck lê o token via env var 'motherduck_token'
os.environ["motherduck_token"] = TOKEN

# 1) Conecta ao "hub" do MotherDuck (sem DB específico)
con = duckdb.connect("md:?saas_mode=true")

# 2) Cria (se não existir) e entra no DB
con.execute(f"CREATE DATABASE IF NOT EXISTS {DBNAME}")
con.execute(f"USE {DBNAME}")

# 3) Sobe o Parquet para uma tabela (substitui se já existir)
path = pathlib.Path(PARQUET)
if not path.exists():
    sys.exit(f"Parquet não encontrado: {path}")

con.execute(f"""
    CREATE OR REPLACE TABLE {TABLE} AS
    SELECT * FROM read_parquet('{path.as_posix()}')
""")

# 4) Teste: quantas linhas tem de SP?
n = con.execute(f"SELECT COUNT(*) FROM {TABLE} WHERE CD_UF = '{UF_CODE}'").fetchone()[0]
print(f"OK! {TABLE} no DB '{DBNAME}' com {n:,} linhas de SP.")

con.close()
