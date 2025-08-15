import duckdb, os, pathlib

# 1) Autenticação — pegue seu token no MotherDuck e guarde numa env var
os.environ["motherduck_token"] = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJlbWFpbCI6ImhpbGFsaXNrYW5kYXJAZ21haWwuY29tIiwic2Vzc2lvbiI6ImhpbGFsaXNrYW5kYXIuZ21haWwuY29tIiwicGF0IjoiSndLRXhHSGx2TXRJME5lTTROOTA1WWMwSlhyUEs5OGV6UnB0QWFJeVJPYyIsInVzZXJJZCI6IjI2ODYxMmY0LWFhNWYtNGUxZi1hOWMzLTAxYzFmM2IyYjNhMyIsImlzcyI6Im1kX3BhdCIsInJlYWRPbmx5IjpmYWxzZSwidG9rZW5UeXBlIjoicmVhZF93cml0ZSIsImlhdCI6MTc1NTIyOTA1Mn0.TYmOwWMJYIUbVHuLrislouNIDGco9N6Re2Gpm2trObc"  # ou use keyring/.env

# 2) Conecta no MD (usa o token automaticamente)
con = duckdb.connect("md:sensocenso")  # "md:<nome_do_db>"

# 3) (opcional p/ HTTP) con.execute("INSTALL httpfs; LOAD httpfs;")

# 4) Carrega do Parquet local para uma TABELA no MD
parquet = r"D:\repo\saida_parquet\base_integrada_final.parquet"
con.execute(f"CREATE OR REPLACE TABLE censo2022 AS SELECT * FROM read_parquet('{pathlib.Path(parquet).as_posix()}')")
con.close()