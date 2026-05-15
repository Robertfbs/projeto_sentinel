import sqlite3
import pandas as pd

conn = sqlite3.connect("pre_contencioso.db")

# Ler tabela
df = pd.read_sql("SELECT * FROM tickets", conn)

print(df.head())