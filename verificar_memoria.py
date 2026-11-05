import sqlite3

c = sqlite3.connect(r"C:\Jarvis\memoria.db")

print("Tabelas encontradas:")

tabelas = c.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

for tabela in tabelas:
    print("-", tabela[0])

c.close()
