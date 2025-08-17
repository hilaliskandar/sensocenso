import duckdb, os, pathlib

# 1) Autenticação — pegue seu token no MotherDuck e guarde numa env var
# O token MotherDuck deve ser definido na variável de ambiente 'motherduck_token'
if "motherduck_token" not in os.environ:
    raise RuntimeError("O token MotherDuck não foi encontrado na variável de ambiente 'motherduck_token'. Defina-o antes de executar este script.")

# 2) Conecta no MD (usa o token automaticamente)
con = duckdb.connect("md:sensocenso")  # "md:<nome_do_db>"

# 3) (opcional p/ HTTP) con.execute("INSTALL httpfs; LOAD httpfs;")

# 4) Carrega do Parquet local para uma TABELA no MD
parquet = r"D:\repo\saida_parquet\base_integrada_final.parquet"
con.execute(f"CREATE OR REPLACE TABLE censo2022 AS SELECT * FROM read_parquet('{pathlib.Path(parquet).as_posix()}')")
con.close()
