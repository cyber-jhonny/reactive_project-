import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
from google import genai
from google.genai import types


MODELO_IMAGEM = "gemini-3-pro-image"
RESOLUCAO_PADRAO = "2K"
PROPORCAO_PADRAO = "16:9"


def gerar_imagem(prompt, aspect_ratio=PROPORCAO_PADRAO,
                 image_size=RESOLUCAO_PADRAO):

    prompt = prompt.strip()

    if not prompt:
        raise ValueError("Digite uma descricao para gerar a imagem.")

    raiz_projeto = Path(__file__).resolve().parent.parent
    arquivo_env = raiz_projeto / ".env"

    load_dotenv(arquivo_env)

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY nao encontrada no arquivo .env."
        )

    cliente = genai.Client(api_key=api_key)

    resposta = cliente.models.generate_content(
        model=MODELO_IMAGEM,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(
                aspect_ratio=aspect_ratio,
                image_size=image_size
            )
        )
    )

    pasta_imagens = raiz_projeto / "imagens"
    pasta_imagens.mkdir(parents=True, exist_ok=True)

    for parte in resposta.parts:
        if parte.inline_data is not None:
            mime = parte.inline_data.mime_type or "image/png"

            extensao = {
                "image/png": ".png",
                "image/jpeg": ".jpg",
                "image/webp": ".webp"
            }.get(mime, ".png")

            nome = datetime.now().strftime(
                "jarvis_%Y%m%d_%H%M%S_%f"
            )

            destino = pasta_imagens / f"{nome}{extensao}"

            destino.write_bytes(parte.inline_data.data)

            return destino

    raise RuntimeError(
        "A API respondeu, mas nao retornou uma imagem."
    )
