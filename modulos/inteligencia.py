import json
import os
import urllib.request
import urllib.error
from modulos.caminhos import ENV_FILE

from dotenv import load_dotenv

from modulos.memoria import (
    consultar_memorias,
    historico_recente,
    salvar_mensagem
)

load_dotenv(ENV_FILE)

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://127.0.0.1:11434/api/chat"
)

MODELO = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

INSTRUCOES = """
Você é JARVIS, um assistente pessoal inteligente.
Fale sempre em português brasileiro.
Seja natural, inteligente e objetivo.
Responda como em uma conversa por voz.
Prefira respostas curtas, claras e naturais.
Evite listas longas e explicações desnecessárias.
Não invente informações, notícias ou dados atuais.
Nunca diga que executou uma ação sem realmente executá-la.
"""


def consultar_ollama(mensagens):
    dados = {
        "model": MODELO,
        "stream": False,
        "messages": mensagens,
        "options": {
            "temperature": 0.7
        }
    }

    requisicao = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(dados, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(requisicao, timeout=180) as resposta:
            resultado = json.loads(
                resposta.read().decode("utf-8")
            )

        texto = resultado.get("message", {}).get("content", "")

        if texto and texto.strip():
            return texto.strip()

        return "Não consegui formular uma resposta."

    except Exception as erro:
        print(f"[Ollama] {str(erro)[:300]}")
        return "Estou com dificuldade para acessar minha inteligência local."


def conversar(pergunta, conversation_id=None):
    mensagens = historico_recente(8, conversation_id)
    memorias = consultar_memorias(10)

    contexto_memorias = "\n".join(
        f"- [{kind}] {content}"
        for _, kind, content in memorias
    )

    mensagens_ollama = [
        {
            "role": "system",
            "content": (
                INSTRUCOES
                + "\n\nMEMÓRIAS:\n"
                + (contexto_memorias or "Nenhuma memória cadastrada.")
            )
        }
    ]

    for role, content in mensagens:
        if role in ("user", "assistant") and content:
            mensagens_ollama.append({
                "role": role,
                "content": str(content)
            })

    salvar_mensagem("user", pergunta, conversation_id)

    mensagens_ollama.append({
        "role": "user",
        "content": pergunta
    })

    resposta = consultar_ollama(mensagens_ollama)

    if resposta and not resposta.startswith(
        "Estou com dificuldade para acessar"
    ):
        salvar_mensagem("assistant", resposta, conversation_id)

    return resposta