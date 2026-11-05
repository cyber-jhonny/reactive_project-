from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sqlite3
import sys
import textwrap

arquivo = Path(r"C:\Jarvis\modulos\conversa_ao_vivo.py")
codigo = arquivo.read_text(encoding="utf-8-sig")
linhas = codigo.splitlines(keepends=True)

# Localizar o receptor.
receptor = next(
    (i for i, linha in enumerate(linhas)
     if "async for message in session.receive():" in linha),
    None
)

if receptor is None:
    raise SystemExit("ERRO: receptor Live nao encontrado.")

inicio = next(
    (i for i in range(receptor + 1, len(linhas))
     if 'tool_call = getattr(message, "tool_call", None)' in linhas[i]),
    None
)

fim = next(
    (i for i in range(inicio + 1, len(linhas))
     if "recebeu_mensagem = True" in linhas[i]),
    None
) if inicio is not None else None

if inicio is None or fim is None:
    raise SystemExit("ERRO: bloco incorreto nao localizado.")

# O codigo dentro do async for precisa de quatro espacos adicionais.
indent_receptor = len(linhas[receptor]) - len(linhas[receptor].lstrip())
indentacao = " " * (indent_receptor + 4)

bloco = """
tool_call = getattr(message, "tool_call", None)

if tool_call:
    function_responses = []

    for fc in (getattr(tool_call, "function_calls", None) or []):
        nome = getattr(fc, "name", "")
        argumentos = getattr(fc, "args", {}) or {}

        if nome == "buscar_historico_antigo":
            consulta = str(argumentos.get("consulta", ""))

            try:
                resultado = buscar_historico_antigo(
                    consulta,
                    limite=6,
                    max_chars=10000
                )
            except Exception as exc:
                resultado = "Erro ao pesquisar memoria: " + str(exc)[:300]
        else:
            resultado = "Ferramenta nao disponivel."

        function_responses.append(
            types.FunctionResponse(
                id=fc.id,
                name=nome,
                response={"resultado": resultado}
            )
        )

    if function_responses:
        await session.send_tool_response(
            function_responses=function_responses
        )
"""

novo_bloco = textwrap.indent(
    bloco.strip("\n"),
    indentacao
) + "\n"

# Backup antes de corrigir.
backup = arquivo.with_name(
    "conversa_ao_vivo.pre_reparo_"
    + datetime.now().strftime("%Y%m%d_%H%M%S")
    + ".py"
)
shutil.copy2(arquivo, backup)

linhas[inicio:fim] = [novo_bloco]
novo_codigo = "".join(linhas)

# Verificar sintaxe antes de gravar.
compile(novo_codigo, str(arquivo), "exec")
arquivo.write_text(novo_codigo, encoding="utf-8")

# Validar compilacao.
py_compile.compile(str(arquivo), doraise=True)
py_compile.compile(
    r"C:\Jarvis\modulos\memoria_contextual.py",
    doraise=True
)

# Validar importacao e busca.
sys.path.insert(0, r"C:\Jarvis")

from modulos.conversa_ao_vivo import LiveVoiceWorker
from modulos.memoria_contextual import (
    contexto_inicial,
    buscar_historico_antigo
)

contexto = contexto_inicial(limite_mensagens=10)
resultado = buscar_historico_antigo(
    "FiveM computador desempenho",
    limite=3
)

# Confirmar que o banco permanece acessivel.
con = sqlite3.connect(
    "file:C:/Jarvis/memoria.db?mode=ro",
    uri=True
)
mensagens = con.execute(
    "SELECT COUNT(*) FROM messages"
).fetchone()[0]
memorias = con.execute(
    "SELECT COUNT(*) FROM memories WHERE active=1"
).fetchone()[0]
con.close()

print("\n=== RESULTADO DO REPARO ===")
print("Compilacao do Live: OK")
print("Importacao do Live: OK")
print("Memoria contextual: OK")
print("Busca historica:", len(resultado), "caracteres")
print("Contexto inicial:", len(contexto), "caracteres")
print("Mensagens preservadas:", mensagens)
print("Memorias ativas:", memorias)
print("Voz Algenib:", 'voice_name": "Algenib"' in novo_codigo)
print("Backup:", backup)
print("\nREPARO CONCLUIDO COM SUCESSO.")
