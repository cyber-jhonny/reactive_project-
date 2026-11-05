
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher

from modulos.caminhos import CATALOG_PATH

ALIASES = {
    "navegador": (
        "chrome", "edge", "firefox", "brave", "opera"
    ),
    "programa de lives": ("obs studio", "obs"),
    "programa de streaming": ("obs studio", "obs"),
    "gravacao de lives": ("obs studio", "obs"),
    "musica": ("spotify",),
    "mensagens": ("discord",),
    "editor de video": (
        "davinci resolve", "capcut", "filmora",
        "premiere", "shotcut"
    ),
}

_BLOQUEADOS = re.compile(
    r"\b(uninstall|uninstaller|desinstalar|desinstalador)\b",
    re.IGNORECASE
)

def normalizar(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    return re.sub(r"[^a-z0-9]+", " ", texto.lower()).strip()


def _carregar():
    if not CATALOG_PATH.exists():
        raise FileNotFoundError(
            "Catalogo de aplicativos nao encontrado. "
            "Atualize o inventario do Windows."
        )

    with CATALOG_PATH.open("r", encoding="utf-8-sig") as f:
        dados = json.load(f)

    escolhidos = {}

    prioridade = {
        "shortcut": 0,
        "appx": 1,
        "exe": 2
    }

    for item in dados.get("apps", []):
        nome = str(item.get("name") or "").strip()
        tipo = str(item.get("type") or "").lower()
        origem = str(item.get("source") or "").lower()
        destino = str(item.get("target") or "").strip()

        if not nome or not destino or _BLOQUEADOS.search(nome):
            continue

        # Nao executar executaveis encontrados apenas no PATH.
        # So aceitamos EXEs registrados como aplicativos instalados.
        if tipo == "exe" and "registro do windows" not in origem:
            continue

        if tipo not in ("shortcut", "appx", "exe"):
            continue

        if tipo == "shortcut":
            if not destino.lower().endswith(".lnk"):
                continue
            if not Path(destino).is_file():
                continue

        elif tipo == "appx":
            if "!" not in destino:
                continue

        elif tipo == "exe":
            if not Path(destino).is_file():
                continue

        chave = normalizar(nome)
        if not chave:
            continue

        atual = escolhidos.get(chave)

        if (
            atual is None
            or prioridade[tipo] < prioridade.get(atual["type"], 99)
        ):
            escolhidos[chave] = {
                "name": nome,
                "type": tipo,
                "target": destino,
                "source": item.get("source", "")
            }

    return list(escolhidos.values())


def _pontuar(consulta, nome):
    if consulta == nome:
        return 100

    if consulta in nome:
        return 94

    if nome in consulta:
        return 88

    tokens_q = set(consulta.split())
    tokens_n = set(nome.split())

    if tokens_q and tokens_q.issubset(tokens_n):
        return 92

    if tokens_q and tokens_n:
        sobreposicao = len(tokens_q & tokens_n) / len(tokens_q)
    else:
        sobreposicao = 0

    semelhanca = SequenceMatcher(None, consulta, nome).ratio()
    return max(sobreposicao * 82, semelhanca * 78)


def _buscar(consulta, limite=12):
    q = normalizar(consulta)

    if not q:
        return []

    apps = _carregar()
    candidatos = []

    sinonimos = ALIASES.get(q, ())

    for app in apps:
        nome = normalizar(app["name"])
        score = _pontuar(q, nome)

        if sinonimos and any(
            normalizar(s) in nome for s in sinonimos
        ):
            score = max(score, 76)

        if score >= 35:
            candidatos.append((score, app))

    candidatos.sort(
        key=lambda x: (x[0], x[1]["name"].lower()),
        reverse=True
    )

    return candidatos[:limite]


def buscar_aplicativos_instalados(termo, limite=12):
    encontrados = _buscar(termo, limite)

    if not encontrados:
        return "Nao encontrei aplicativos correspondentes no catalogo local."

    linhas = ["APLICATIVOS ENCONTRADOS NO COMPUTADOR:"]

    for score, app in encontrados:
        linhas.append(
            f"- {app['name']} | tipo: {app['type']} "
            f"| origem: {app['source']}"
        )

    return "\n".join(linhas)


def resolver_app_por_comando(termo):
    encontrados = _buscar(termo, limite=5)

    if not encontrados:
        return None

    score, primeiro = encontrados[0]

    if score < 88:
        return None

    if len(encontrados) > 1:
        score2, segundo = encontrados[1]

        if (
            normalizar(primeiro["name"]) != normalizar(segundo["name"])
            and score - score2 < 7
        ):
            return None

    return primeiro["name"]


def abrir_aplicativo_catalogo(nome):
    encontrados = _buscar(nome, limite=5)

    if not encontrados:
        return (
            f"Nao encontrei o aplicativo '{nome}'. "
            "Posso pesquisar outras correspondencias."
        )

    score, app = encontrados[0]

    if score < 88:
        return (
            f"Nao encontrei correspondencia suficientemente segura "
            f"para '{nome}'.\n"
            + buscar_aplicativos_instalados(nome, 8)
        )

    if len(encontrados) > 1:
        score2, segundo = encontrados[1]

        if (
            normalizar(app["name"]) != normalizar(segundo["name"])
            and score - score2 < 7
        ):
            return (
                "Encontrei mais de um aplicativo possivel. "
                "Escolha um nome mais especifico:\n"
                + buscar_aplicativos_instalados(nome, 8)
            )

    try:
        if app["type"] == "appx":
            os.startfile("shell:AppsFolder\\" + app["target"])

        elif app["type"] == "shortcut":
            os.startfile(app["target"])

        elif app["type"] == "exe":
            caminho = Path(app["target"])

            subprocess.Popen(
                [str(caminho)],
                cwd=str(caminho.parent),
                shell=False
            )

        else:
            return "Tipo de aplicativo nao autorizado."

        return f"{app['name']} foi iniciado com sucesso."

    except Exception as exc:
        return f"Nao consegui abrir {app['name']}: {exc}"
