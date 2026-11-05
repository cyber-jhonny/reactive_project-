
import re
import unicodedata

from modulos.catalogo_apps import (
    buscar_aplicativos_instalados,
    abrir_aplicativo_catalogo,
)
from modulos.memoria_contextual import buscar_historico_antigo
from modulos.internet import executar_comando_internet


TOOL_DECLARATIONS = [
    {
        "name": "buscar_aplicativos_instalados",
        "description": (
            "Pesquisa o catalogo local de aplicativos instalados no Windows. "
            "Use quando nao souber o nome exato de um programa. "
            "Nao inicia nenhum aplicativo."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "termo": {
                    "type": "STRING",
                    "description": "Nome, categoria ou funcao do aplicativo."
                }
            },
            "required": ["termo"]
        }
    },
    {
        "name": "abrir_aplicativo",
        "description": (
            "Abre um aplicativo identificado no catalogo local do Windows. "
            "Use apenas quando o usuario solicitar a abertura do programa."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "nome": {
                    "type": "STRING",
                    "description": "Nome do aplicativo que deve ser aberto."
                }
            },
            "required": ["nome"]
        }
    },
    {
        "name": "pesquisar_internet",
        "description": "Pesquisa informacoes atuais na internet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "consulta": {"type": "STRING"}
            },
            "required": ["consulta"]
        }
    },
    {
        "name": "consultar_noticias",
        "description": "Pesquisa noticias recentes sobre um tema.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "tema": {"type": "STRING"}
            },
            "required": ["tema"]
        }
    },
    {
        "name": "consultar_clima",
        "description": "Consulta a previsao do tempo de uma cidade.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "cidade": {"type": "STRING"}
            },
            "required": ["cidade"]
        }
    },
    {
        "name": "abrir_site",
        "description": "Abre um endereco de site no navegador.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "ler_pagina",
        "description": "Le e resume uma pagina publica da internet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "preparar_download",
        "description": (
            "Prepara um download permitido. Nao conclui o download. "
            "Depois, informe ao usuario que ele deve dizer "
            "'confirmar download' para iniciar."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {"type": "STRING"}
            },
            "required": ["url"]
        }
    },
    {
        "name": "confirmar_download",
        "description": (
            "Confirma um download pendente SOMENTE quando a ultima fala "
            "do usuario for exatamente uma confirmacao explicita, como "
            "'confirmar download', 'confirmo download' ou 'pode baixar'."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "confirmacao": {"type": "STRING"}
            },
            "required": ["confirmacao"]
        }
    },
    {
        "name": "cancelar_download",
        "description": "Cancela um download pendente quando o usuario solicitar.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "confirmacao": {"type": "STRING"}
            },
            "required": ["confirmacao"]
        }
    },
    {
        "name": "buscar_historico_antigo",
        "description": (
            "Pesquisa conversas antigas no banco SQLite do usuario. "
            "Use para recuperar informacoes de projetos, preferencias "
            "ou assuntos discutidos anteriormente."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "consulta": {"type": "STRING"}
            },
            "required": ["consulta"]
        }
    },
]


def _normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", texto.lower()).strip()


def _internet(acao, **dados):
    resultado = executar_comando_internet({
        "acao": acao,
        **dados
    })

    if not isinstance(resultado, str):
        resultado = str(resultado)

    return resultado[:12000]


def executar_ferramenta(nome, argumentos, texto_usuario=""):
    argumentos = argumentos or {}

    try:
        if nome == "buscar_aplicativos_instalados":
            return buscar_aplicativos_instalados(
                str(argumentos.get("termo", "")),
                limite=12
            )

        if nome == "abrir_aplicativo":
            nome_app = str(argumentos.get("nome", "")).strip()

            if not nome_app:
                return "Informe o nome do aplicativo."

            return abrir_aplicativo_catalogo(nome_app)

        if nome == "pesquisar_internet":
            consulta = str(argumentos.get("consulta", "")).strip()
            if not consulta:
                return "Informe o que deve ser pesquisado."
            return _internet("pesquisar", consulta=consulta)

        if nome == "consultar_noticias":
            tema = str(argumentos.get("tema", "")).strip() or "Brasil"
            return _internet("noticias", consulta=tema)

        if nome == "consultar_clima":
            cidade = str(argumentos.get("cidade", "")).strip() or "Salvador"
            return _internet("clima", cidade=cidade)

        if nome == "abrir_site":
            url = str(argumentos.get("url", "")).strip()
            return _internet("abrir_site", url=url)

        if nome == "ler_pagina":
            url = str(argumentos.get("url", "")).strip()
            return _internet("ler_pagina", url=url)

        if nome == "preparar_download":
            url = str(argumentos.get("url", "")).strip()
            return _internet("download", url=url)

        if nome == "confirmar_download":
            frase = _normalizar(texto_usuario)
            frase = re.sub(r"^jarvis[\s,:-]*", "", frase).strip(" .!?")

            confirmacoes = {
                "confirmar download",
                "confirmo download",
                "pode baixar",
            }

            if frase not in confirmacoes:
                return (
                    "Download nao confirmado. Aguarde a solicitacao "
                    "do usuario dizer explicitamente 'confirmar download'."
                )

            return _internet("confirmar_download")

        if nome == "cancelar_download":
            frase = _normalizar(texto_usuario)
            frase = re.sub(r"^jarvis[\s,:-]*", "", frase).strip(" .!?")

            cancelamentos = {
                "cancelar download",
                "cancela download",
                "nao baixar",
            }

            if frase not in cancelamentos:
                return "Para cancelar, aguarde uma solicitacao explicita do usuario."

            return _internet("cancelar_download")

        if nome == "buscar_historico_antigo":
            consulta = str(argumentos.get("consulta", "")).strip()

            if not consulta:
                return "Informe o assunto a procurar na memoria."

            return buscar_historico_antigo(
                consulta,
                limite=6,
                max_chars=10000
            )

        return "Ferramenta nao reconhecida ou nao autorizada."

    except Exception as exc:
        return f"Falha ao executar {nome}: {type(exc).__name__}: {exc}"
