from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys

ROOT = Path(r"C:\Jarvis")
MODULOS = ROOT / "modulos"
LIVE = MODULOS / "conversa_ao_vivo.py"
MEMORIA = MODULOS / "memoria_contextual.py"

if not LIVE.exists():
    raise SystemExit("ERRO: conversa_ao_vivo.py nao encontrado.")

# Backups.
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_live = ROOT / f"conversa_ao_vivo.backup_memoria_{stamp}.py"
shutil.copy2(LIVE, backup_live)

if MEMORIA.exists():
    shutil.copy2(
        MEMORIA,
        ROOT / f"memoria_contextual.backup_{stamp}.py"
    )

# Novo modulo de busca historica, somente leitura.
memory_code = r'''
import re
import sqlite3
import unicodedata
from pathlib import Path


DB_PATH = Path(r"C:\Jarvis\memoria.db")

STOPWORDS = {
    "que", "para", "com", "uma", "uns", "umas", "dos", "das",
    "por", "qual", "quais", "quando", "onde", "como", "porque",
    "sobre", "entre", "mais", "muito", "essa", "esse", "isso",
    "este", "esta", "aquela", "aquele", "meu", "minha", "seu",
    "sua", "tem", "ter", "ser", "foi", "era", "sao", "estao",
    "the", "and", "for", "with", "from", "this", "that", "you"
}


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto.lower()).strip()


def _termos(texto):
    normalizado = _normalizar(texto)
    palavras = re.findall(r"[a-z0-9_]{2,}", normalizado)
    return list(dict.fromkeys(
        p for p in palavras
        if p not in STOPWORDS
    ))


def _conectar():
    if not DB_PATH.exists():
        raise FileNotFoundError("Banco de memoria nao encontrado.")

    db = sqlite3.connect(str(DB_PATH), timeout=10)
    db.row_factory = sqlite3.Row
    return db


def contexto_inicial(conversation_id=None, limite_mensagens=14):
    partes = []

    with _conectar() as db:

        # Todas as memorias permanentes ativas.
        memorias = db.execute("""
            SELECT kind, content
            FROM memories
            WHERE active = 1
            ORDER BY updated_at DESC
        """).fetchall()

        if memorias:
            partes.append("MEMORIAS PERMANENTES:")
            for item in memorias:
                partes.append(
                    f"- [{item['kind']}] {item['content']}"
                )

        # Resumos que eventualmente tenham sido criados.
        try:
            resumos = db.execute("""
                SELECT summary
                FROM summaries
                ORDER BY id DESC
                LIMIT 5
            """).fetchall()

            if resumos:
                partes.append("\nRESUMOS DE CONVERSAS ANTIGAS:")
                for item in reversed(resumos):
                    partes.append("- " + item["summary"])

        except sqlite3.Error:
            pass

        # Historico recente da conversa aberta.
        if conversation_id is not None:
            atuais = db.execute("""
                SELECT role, content, created_at
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (conversation_id, limite_mensagens)).fetchall()

            if atuais:
                partes.append("\nCONVERSA ATUAL:")
                for item in reversed(atuais):
                    partes.append(
                        f"{item['role']}: {item['content']}"
                    )

        # Contexto recente das demais conversas.
        recentes = db.execute("""
            SELECT m.id, m.role, m.content, m.conversation_id,
                   c.title
            FROM messages m
            LEFT JOIN conversations c
                ON c.id = m.conversation_id
            ORDER BY m.id DESC
            LIMIT 14
        """).fetchall()

        if recentes:
            partes.append("\nATIVIDADE RECENTE DO USUARIO:")
            for item in reversed(recentes):
                if (
                    conversation_id is not None
                    and item["conversation_id"] == conversation_id
                ):
                    continue

                titulo = item["title"] or "Conversa antiga"
                partes.append(
                    f"[{titulo}] {item['role']}: {item['content']}"
                )

    resultado = "\n".join(partes)

    # Evitar carregar contexto excessivo na abertura.
    return resultado[:18000]


def buscar_historico_antigo(consulta, limite=6, max_chars=10000):
    termos = _termos(consulta)

    if not termos:
        return "A consulta nao possui termos suficientes para pesquisar."

    with _conectar() as db:
        rows = db.execute("""
            SELECT m.id, m.role, m.content, m.created_at,
                   m.conversation_id, c.title
            FROM messages m
            LEFT JOIN conversations c
                ON c.id = m.conversation_id
            ORDER BY m.id ASC
        """).fetchall()

    if not rows:
        return "O historico de conversas esta vazio."

    grupos = {}

    for row in rows:
        key = row["conversation_id"]
        grupos.setdefault(key, []).append(row)

    resultados = []

    frase = _normalizar(consulta)

    for key, mensagens in grupos.items():
        for indice, row in enumerate(mensagens):
            texto = _normalizar(row["content"])
            pontuacao = 0

            for termo in termos:
                ocorrencias = texto.count(termo)
                if ocorrencias:
                    pontuacao += min(ocorrencias, 3) * 2

            if frase and len(frase) >= 5 and frase in texto:
                pontuacao += 8

            if pontuacao:
                resultados.append((
                    pontuacao,
                    row["id"],
                    mensagens,
                    indice
                ))

    if not resultados:
        return (
            "Nao encontrei mensagens antigas diretamente relacionadas "
            "a esta consulta no banco de dados."
        )

    resultados.sort(
        key=lambda item: (item[0], item[1]),
        reverse=True
    )

    selecionados = []
    ids_incluidos = set()

    for pontuacao, message_id, mensagens, indice in resultados:
        inicio = max(0, indice - 1)
        fim = min(len(mensagens), indice + 2)

        trecho = mensagens[inicio:fim]
        novos = [m for m in trecho if m["id"] not in ids_incluidos]

        if not novos:
            continue

        selecionados.append(
            (pontuacao, message_id, mensagens[inicio]["title"], novos)
        )

        for item in novos:
            ids_incluidos.add(item["id"])

        if len(selecionados) >= limite:
            break

    partes = ["RESULTADOS RECUPERADOS DO HISTORICO COMPLETO:"]

    for pontuacao, message_id, titulo, trecho in selecionados:
        partes.append(
            f"\nConversa: {titulo or 'Conversa antiga'}"
        )

        for item in trecho:
            texto = str(item["content"])[:1400]
            partes.append(f"{item['role']}: {texto}")

    resultado = "\n".join(partes)

    return resultado[:max_chars]
'''

MEMORIA.write_text(memory_code, encoding="utf-8")

# Atualizar o worker Live.
codigo = LIVE.read_text(encoding="utf-8-sig")

import_line = (
    "from modulos.memoria_contextual import "
    "contexto_inicial, buscar_historico_antigo"
)

if import_line not in codigo:
    marker = "\n\nLIVE_MODEL = "
    if marker not in codigo:
        raise RuntimeError("Nao encontrei o ponto de imports no Live.")
    codigo = codigo.replace(
        marker,
        "\n" + import_line + marker,
        1
    )

# Trocar build_instructions por uma versao com memoria completa.
start = codigo.find("    def build_instructions(self):")
end = codigo.find("    async def send_audio(", start)

if start < 0 or end < 0:
    raise RuntimeError("Nao consegui localizar build_instructions.")

novo_metodo = r'''
    def build_instructions(self):
        parts = [
            "Voce e JARVIS, assistente pessoal do usuario.",
            "Fale sempre em portugues brasileiro.",
            "Converse naturalmente, com respostas claras e objetivas.",
            "O usuario pode interromper sua fala a qualquer momento.",
            "Utilize as memorias permanentes e o historico fornecido.",
            "Quando perguntarem sobre conversas antigas, projetos, "
            "preferencias ou fatos anteriores, consulte a ferramenta "
            "buscar_historico_antigo antes de responder.",
            "Nao invente lembrancas. Se nao encontrar uma informacao, "
            "diga claramente que nao encontrou registro.",
            "Nao afirme que salvou uma memoria sem realmente salva-la.",
            "Nao exponha dados pessoais sem necessidade."
        ]

        try:
            contexto = contexto_inicial(
                conversation_id=self.get_conversation(),
                limite_mensagens=14
            )

            if contexto:
                parts.append(
                    "\nCONTEXTO RECUPERADO DO BANCO SQLITE:\n" + contexto
                )

        except Exception as exc:
            print("[MEMORIA LIVE]", str(exc)[:200])

        parts.append(
            "\nFERRAMENTA DE MEMORIA:\n"
            "Voce possui a ferramenta buscar_historico_antigo. "
            "Use-a quando uma pergunta depender de conversas anteriores, "
            "informacoes antigas ou detalhes de projetos. "
            "A ferramenta pesquisa todas as conversas salvas no SQLite. "
            "Leia os resultados antes de responder."
        )

        return "\n\n".join(parts)

'''

codigo = codigo[:start] + novo_metodo + codigo[end:]

# Disponibilizar busca historica como ferramenta para o Gemini.
tool_marker = '            "response_modalities": ["AUDIO"],'

tool_config = r'''
            "tools": [{
                "function_declarations": [{
                    "name": "buscar_historico_antigo",
                    "description": (
                        "Pesquisa todas as conversas antigas do usuario "
                        "no banco SQLite. Use antes de responder perguntas "
                        "sobre fatos, projetos, preferencias ou assuntos "
                        "discutidos anteriormente."
                    ),
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "consulta": {
                                "type": "STRING",
                                "description": (
                                    "Tema, palavra-chave ou informacao "
                                    "que deve ser procurada no historico."
                                )
                            }
                        },
                        "required": ["consulta"]
                    }
                }]
            }],
'''

if '"name": "buscar_historico_antigo"' not in codigo:
    if tool_marker not in codigo:
        raise RuntimeError("Nao encontrei response_modalities na configuracao.")
    codigo = codigo.replace(
        tool_marker,
        tool_marker + "\n" + tool_config,
        1
    )

# Atender chamadas de ferramenta recebidas pela API Live.
if 'tool_call = getattr(message, "tool_call", None)' not in codigo:
    receiver_marker = "async for message in session.receive():"

    pos = codigo.find(receiver_marker)
    if pos < 0:
        raise RuntimeError("Nao encontrei o receptor de mensagens Live.")

    line_end = codigo.find("\n", pos)
    indent = len(codigo[pos:]) - len(codigo[pos:].lstrip())

    block = r'''
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
'''

    import textwrap
    indentacao = " " * indent
    bloco_formatado = textwrap.indent(
        block.strip("\n"),
        indentacao
    )

    codigo = (
        codigo[:line_end + 1]
        + bloco_formatado
        + "\n"
        + codigo[line_end + 1:]
    )

LIVE.write_text(codigo, encoding="utf-8")

# Compilar e testar sem modificar o banco.
py_compile.compile(str(MEMORIA), doraise=True)
py_compile.compile(str(LIVE), doraise=True)

sys.path.insert(0, str(ROOT))

from modulos.memoria_contextual import (
    contexto_inicial,
    buscar_historico_antigo
)

contexto = contexto_inicial(limite_mensagens=10)
resultado = buscar_historico_antigo(
    "FiveM computador desempenho",
    limite=3
)

print("\n=== TESTE DE MEMORIA ===")
print("Memoria inicial carregada:", bool(contexto))
print("Contexto inicial:", len(contexto), "caracteres")
print("Busca historica funcional:", "RESULTADOS RECUPERADOS" in resultado)
print("Resultado da busca:", len(resultado), "caracteres")

print("\n=== VALIDACAO ===")
print("Modulo de memoria: OK")
print("Modulo Live: OK")
print("Compilacao: OK")
print("Banco original: preservado")
print("Backup do Live:", backup_live)
print("\nATUALIZACAO CONCLUIDA.")
