import sqlite3

c = sqlite3.connect(r"C:\Jarvis\memoria.db")

for tabela in ["messages", "memories", "summaries"]:
    print(f"\n===== {tabela.upper()} =====")

    colunas = c.execute(
        f"PRAGMA table_info({tabela})"
    ).fetchall()

    for coluna in colunas:
        print(f"Coluna: {coluna[1]} | Tipo: {coluna[2]}")

c.close()
