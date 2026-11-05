import sqlite3
from datetime import datetime
from pathlib import Path

from modulos.caminhos import DATABASE_PATH

BANCO = DATABASE_PATH

def conectar():
    return sqlite3.connect(BANCO)


def inicializar_conversas():
    agora = datetime.now().isoformat()

    with conectar() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        colunas = [
            coluna[1]
            for coluna in db.execute(
                "PRAGMA table_info(messages)"
            ).fetchall()
        ]

        if "conversation_id" not in colunas:
            db.execute(
                "ALTER TABLE messages ADD COLUMN conversation_id INTEGER"
            )

        antigas = db.execute("""
            SELECT COUNT(*)
            FROM messages
            WHERE conversation_id IS NULL
        """).fetchone()[0]

        if antigas:
            anterior = db.execute("""
                SELECT id FROM conversations
                WHERE title = 'Histórico anterior'
                ORDER BY id LIMIT 1
            """).fetchone()

            if anterior:
                id_anterior = anterior[0]
            else:
                cursor = db.execute("""
                    INSERT INTO conversations
                    (title, created_at, updated_at)
                    VALUES (?, ?, ?)
                """, ("Histórico anterior", agora, agora))
                id_anterior = cursor.lastrowid

            db.execute("""
                UPDATE messages
                SET conversation_id = ?
                WHERE conversation_id IS NULL
            """, (id_anterior,))

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_conversation
            ON messages(conversation_id, id)
        """)


def criar_conversa(titulo="Nova conversa"):
    agora = datetime.now().isoformat()

    with conectar() as db:
        cursor = db.execute("""
            INSERT INTO conversations
            (title, created_at, updated_at)
            VALUES (?, ?, ?)
        """, (titulo, agora, agora))

        return cursor.lastrowid


def listar_conversas():
    with conectar() as db:
        return db.execute("""
            SELECT id, title, updated_at
            FROM conversations
            ORDER BY updated_at DESC, id DESC
        """).fetchall()


def obter_mensagens_conversa(id_conversa):
    with conectar() as db:
        return db.execute("""
            SELECT id, role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
        """, (id_conversa,)).fetchall()


def renomear_conversa(id_conversa, novo_titulo):
    titulo = novo_titulo.strip()

    if not titulo:
        return False

    with conectar() as db:
        cursor = db.execute("""
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ?
        """, (titulo, datetime.now().isoformat(), id_conversa))

        return cursor.rowcount > 0


def excluir_conversa(id_conversa):
    with conectar() as db:
        db.execute(
            "DELETE FROM messages WHERE conversation_id = ?",
            (id_conversa,)
        )

        cursor = db.execute(
            "DELETE FROM conversations WHERE id = ?",
            (id_conversa,)
        )

        return cursor.rowcount > 0


def salvar_mensagem(role, content, conversation_id=None):
    agora = datetime.now().isoformat()

    with conectar() as db:
        if conversation_id is None:
            existente = db.execute("""
                SELECT id FROM conversations
                ORDER BY id DESC LIMIT 1
            """).fetchone()

            if existente:
                conversation_id = existente[0]
            else:
                cursor = db.execute("""
                    INSERT INTO conversations
                    (title, created_at, updated_at)
                    VALUES (?, ?, ?)
                """, ("Nova conversa", agora, agora))
                conversation_id = cursor.lastrowid

        cursor = db.execute("""
            INSERT INTO messages
            (role, content, created_at, conversation_id)
            VALUES (?, ?, ?, ?)
        """, (role, content, agora, conversation_id))

        db.execute("""
            UPDATE conversations
            SET updated_at = ?
            WHERE id = ?
        """, (agora, conversation_id))

        if role == "user":
            quantidade = db.execute("""
                SELECT COUNT(*)
                FROM messages
                WHERE conversation_id = ?
            """, (conversation_id,)).fetchone()[0]

            if quantidade == 1:
                titulo = content.strip().replace("\n", " ")
                if titulo:
                    db.execute("""
                        UPDATE conversations
                        SET title = ?
                        WHERE id = ? AND title = 'Nova conversa'
                    """, (titulo[:55], conversation_id))

        return cursor.lastrowid


def salvar_memoria(content, kind="fact"):
    agora = datetime.now().isoformat()

    with conectar() as db:
        existente = db.execute("""
            SELECT id FROM memories
            WHERE active = 1 AND LOWER(content) = LOWER(?)
        """, (content.strip(),)).fetchone()

        if existente:
            db.execute("""
                UPDATE memories
                SET updated_at = ?, kind = ?
                WHERE id = ?
            """, (agora, kind, existente[0]))

            return existente[0], False

        cursor = db.execute("""
            INSERT INTO memories
            (kind, content, created_at, updated_at, active)
            VALUES (?, ?, ?, ?, 1)
        """, (kind, content.strip(), agora, agora))

        return cursor.lastrowid, True


def consultar_memorias(limite=20):
    with conectar() as db:
        return db.execute("""
            SELECT id, kind, content
            FROM memories
            WHERE active = 1
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limite,)).fetchall()


def buscar_memoria(termo):
    with conectar() as db:
        return db.execute("""
            SELECT id, kind, content
            FROM memories
            WHERE active = 1 AND content LIKE ?
            ORDER BY updated_at DESC
        """, (f"%{termo}%",)).fetchall()


def esquecer_memoria(id_memoria):
    with conectar() as db:
        cursor = db.execute("""
            UPDATE memories
            SET active = 0, updated_at = ?
            WHERE id = ? AND active = 1
        """, (datetime.now().isoformat(), id_memoria))

        return cursor.rowcount > 0


def historico_recente(limite=12, conversation_id=None):
    with conectar() as db:
        if conversation_id is None:
            mensagens = db.execute("""
                SELECT role, content
                FROM messages
                ORDER BY id DESC
                LIMIT ?
            """, (limite,)).fetchall()
        else:
            mensagens = db.execute("""
                SELECT role, content
                FROM messages
                WHERE conversation_id = ?
                ORDER BY id DESC
                LIMIT ?
            """, (conversation_id, limite)).fetchall()

    return list(reversed(mensagens))


def atualizar_memoria(id_memoria, content, kind):
    agora = datetime.now().isoformat()

    with conectar() as db:
        cursor = db.execute("""
            UPDATE memories
            SET content = ?, kind = ?, updated_at = ?
            WHERE id = ? AND active = 1
        """, (content.strip(), kind, agora, id_memoria))

        return cursor.rowcount > 0


inicializar_conversas()
