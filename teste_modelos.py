import os
from dotenv import load_dotenv
from google import genai

load_dotenv(r"C:\Jarvis\.env")

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options={"timeout": 30000}
)

modelos = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview"
]

for modelo in modelos:
    print(f"\nTestando: {modelo}", flush=True)
    try:
        resposta = client.models.generate_content(
            model=modelo,
            contents="Responda apenas: OK"
        )
        print("FUNCIONOU:", resposta.text, flush=True)
    except Exception as erro:
        print("FALHOU:", str(erro)[:300], flush=True)
