
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from modulos.caminhos import CHROME_PATH, OBS_PATH, STEAM_PATH

APLICATIVOS = {
    "chrome": {
        "nome": "Google Chrome",
        "caminho": CHROME_PATH
    },
    "discord": {
        "nome": "Discord",
        "caminho": os.path.join(
            os.environ["LOCALAPPDATA"], "Discord", "Discord.exe"
        )
    },
    "obs": {
        "nome": "OBS Studio",
        "caminho": OBS_PATH
    },
    "fivem": {
        "nome": "FiveM",
        "caminho": os.path.join(
            os.environ["LOCALAPPDATA"], "FiveM", "FiveM.exe"
        )
    },
    "steam": {
        "nome": "Steam",
        "caminho": STEAM_PATH
    },
    "explorador": {
        "nome": "Explorador de Arquivos",
        "caminho": os.path.join(
            os.environ["WINDIR"], "explorer.exe"
        )
    },
    "spotify": {
        "nome": "Spotify",
        "app_id": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0!Spotify"
    }
}


APELIDOS = [
    ("google chrome", "chrome"),
    ("chrome", "chrome"),
    ("navegador", "chrome"),
    ("discord", "discord"),
    ("obs studio", "obs"),
    ("obs", "obs"),
    ("five m", "fivem"),
    ("fivem", "fivem"),
    ("steam", "steam"),
    ("spotify", "spotify"),
    ("explorador de arquivos", "explorador"),
    ("file explorer", "explorador"),
    ("explorador", "explorador")
]

PALAVRAS_IGNORADAS = {
    "o", "a", "os", "as", "meu", "minha", "meus", "minhas",
    "aplicativo", "aplicativos", "programa", "programas",
    "e", "depois", "em", "seguida", "por", "favor", "pra", "mim"
}


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def detectar_comando(texto):
    texto = normalizar(texto)

    padrao = (
        r"^(?:jarvis\s+)?(?:por favor\s+)?"
        r"(?:abra|abrir|abre|inicie|iniciar|inicia|"
        r"execute|executar|rode|rodar)\s+(.+)$"
    )

    resultado = re.match(padrao, texto)

    if not resultado:
        return None

    restante = resultado.group(1)
    ocupados = [False] * len(restante)
    encontrados = []

    for apelido, chave in sorted(
        APELIDOS, key=lambda item: len(item[0]), reverse=True
    ):
        expressao = r"(?<!\w)" + re.escape(apelido) + r"(?!\w)"

        for ocorrencia in re.finditer(expressao, restante):
            inicio, fim = ocorrencia.span()

            if any(ocupados[inicio:fim]):
                continue

            for posicao in range(inicio, fim):
                ocupados[posicao] = True

            encontrados.append((inicio, chave))

    if not encontrados:
        try:
            from modulos.catalogo_apps import resolver_app_por_comando
            nome_dinamico = resolver_app_por_comando(restante)
            if nome_dinamico:
                return ["catalogo:" + nome_dinamico]
        except Exception:
            pass
        return None

    sobras = "".join(
        " " if ocupados[i] else c
        for i, c in enumerate(restante)
    )

    palavras = normalizar(sobras).split()

    if any(palavra not in PALAVRAS_IGNORADAS for palavra in palavras):
        return None

    encontrados.sort(key=lambda item: item[0])

    resultado = []
    for _, chave in encontrados:
        if chave not in resultado:
            resultado.append(chave)

    return resultado


def verificar_aplicativos():
    resultado = {}

    for chave, dados in APLICATIVOS.items():
        if chave == "spotify":
            resultado[chave] = {
                "nome": dados["nome"],
                "disponivel": True
            }
        else:
            resultado[chave] = {
                "nome": dados["nome"],
                "disponivel": Path(dados["caminho"]).is_file()
            }

    return resultado


def abrir_aplicativos(chaves):
    resultados = []

    for chave in chaves:
        if isinstance(chave, str) and chave.startswith("catalogo:"):
            try:
                from modulos.catalogo_apps import abrir_aplicativo_catalogo
                resultados.append(
                    abrir_aplicativo_catalogo(chave.split(":", 1)[1])
                )
            except Exception as erro:
                resultados.append("Erro no catalogo: " + str(erro))
            continue

        if chave not in APLICATIVOS:
            resultados.append("Aplicativo não autorizado.")
            continue

        dados = APLICATIVOS[chave]

        try:
            if chave == "spotify":
                os.startfile(
                    "shell:AppsFolder\\" + dados["app_id"]
                )
            else:
                caminho = Path(dados["caminho"])

                if not caminho.is_file():
                    resultados.append(
                        f"{dados['nome']}: executável não encontrado."
                    )
                    continue

                subprocess.Popen(
                    [str(caminho)],
                    cwd=str(caminho.parent),
                    shell=False
                )

            resultados.append(f"{dados['nome']} aberto.")

        except Exception as erro:
            resultados.append(
                f"Erro ao abrir {dados['nome']}: {erro}"
            )

    return "\n".join(resultados)
