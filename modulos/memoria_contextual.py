
import re
import sqlite3
import unicodedata
from pathlib import Path


from modulos.caminhos import DATABASE_PATH

DB_PATH = DATABASE_PATH

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
