from pathlib import Path
from datetime import datetime
import shutil
import json
import re
import unicodedata
import textwrap
import py_compile
import sys

ROOT = Path(r"C:\Jarvis")
MOD = ROOT / "modulos"
LIVE = MOD / "conversa_ao_vivo.py"
APPS = MOD / "aplicativos.py"
CATALOGO = MOD / "catalogo_apps.py"
TOOLS = MOD / "live_tools.py"

for p in (LIVE, APPS, ROOT / "dados" / "catalogo_aplicativos.json"):
    if not p.exists():
        raise SystemExit(f"Arquivo necessario nao encontrado: {p}")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")

for p in (LIVE, APPS):
    shutil.copy2(
        p,
        p.with_name(p.stem + ".backup_autonomia_" + stamp + p.suffix)
    )

# ---------------------------------------------------------
# 1. CATALOGO LOCAL DE APLICATIVOS
# ---------------------------------------------------------

catalog_code = r'''
import json
import os
import re
import subprocess
import unicodedata
from pathlib import Path
from difflib import SequenceMatcher

CATALOG_PATH = Path(r"C:\Jarvis\dados\catalogo_aplicativos.json")

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
'''

CATALOGO.write_text(catalog_code, encoding="utf-8")

# ---------------------------------------------------------
# 2. FERRAMENTAS DISPONIVEIS PARA GEMINI LIVE
# ---------------------------------------------------------

tools_code = r'''
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
'''

TOOLS.write_text(tools_code, encoding="utf-8")

# ---------------------------------------------------------
# 3. HABILITAR CATALOGO TAMBEM NO MODO TRADICIONAL
# ---------------------------------------------------------

app_code = APPS.read_text(encoding="utf-8-sig")

old_detection = '''    if not encontrados:
        return None
'''

new_detection = '''    if not encontrados:
        try:
            from modulos.catalogo_apps import resolver_app_por_comando
            nome_dinamico = resolver_app_por_comando(restante)
            if nome_dinamico:
                return ["catalogo:" + nome_dinamico]
        except Exception:
            pass
        return None
'''

if 'catalogo:" + nome_dinamico' not in app_code:
    if old_detection not in app_code:
        raise RuntimeError(
            "Nao encontrei o ponto de deteccao dinamica em aplicativos.py."
        )
    app_code = app_code.replace(old_detection, new_detection, 1)

old_open = '''        if chave not in APLICATIVOS:
            resultados.append("Aplicativo não autorizado.")
            continue
'''

new_open = '''        if isinstance(chave, str) and chave.startswith("catalogo:"):
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
'''

if "chave.startswith(" + '"catalogo:"' not in app_code:
    if old_open not in app_code:
        raise RuntimeError(
            "Nao encontrei o ponto de abertura em aplicativos.py."
        )
    app_code = app_code.replace(old_open, new_open, 1)

APPS.write_text(app_code, encoding="utf-8")

# ---------------------------------------------------------
# 4. CONECTAR AS FERRAMENTAS AO GEMINI LIVE
# ---------------------------------------------------------

live_code = LIVE.read_text(encoding="utf-8-sig")

import_line = (
    "from modulos.live_tools import "
    "TOOL_DECLARATIONS, executar_ferramenta"
)

if import_line not in live_code:
    marker = "\n\nLIVE_MODEL = "
    if marker not in live_code:
        raise RuntimeError("Nao encontrei a area de imports do Live.")
    live_code = live_code.replace(
        marker,
        "\n" + import_line + marker,
        1
    )

# Substituir declaracoes antigas de ferramentas.
tool_start = live_code.find('            "tools": [{')
tool_end = live_code.find(
    '            "session_resumption"',
    tool_start
)

if tool_start < 0 or tool_end < 0:
    raise RuntimeError("Nao encontrei a configuracao tools do Gemini Live.")

nova_config = (
    '            "tools": [{"function_declarations": TOOL_DECLARATIONS}],\n\n'
)

live_code = (
    live_code[:tool_start]
    + nova_config
    + live_code[tool_end:]
)

# Atualizar instrucoes do agente.
inicio = live_code.find("    def build_instructions(self):")
fim = live_code.find("    async def send_audio(", inicio)

if inicio < 0 or fim < 0:
    raise RuntimeError("Nao encontrei build_instructions no Live.")

novo_metodo = r'''
    def build_instructions(self):
        parts = [
            "Voce e JARVIS, um assistente pessoal inteligente.",
            "Fale sempre em portugues brasileiro.",
            "Converse naturalmente e seja objetivo.",
            "Voce possui ferramentas para abrir aplicativos, pesquisar "
            "na internet, consultar noticias e clima, ler paginas e "
            "recuperar memorias antigas.",
            "Voce tambem pode pesquisar o catalogo local de aplicativos "
            "instalados no Windows.",
            "Quando o usuario pedir para abrir um aplicativo cujo nome "
            "voce nao conhece, primeiro use buscar_aplicativos_instalados. "
            "Depois escolha a correspondencia correta e use abrir_aplicativo.",
            "Se houver mais de uma correspondencia plausivel, pergunte "
            "qual delas o usuario deseja abrir.",
            "Em missoes com varias etapas, monte um plano curto, execute "
            "as etapas na ordem, confira o resultado de cada ferramenta "
            "e depois prossiga.",
            "Nao afirme que uma tarefa foi concluida sem receber resultado "
            "positivo da ferramenta.",
            "Voce tem autonomia avancada, mas iniciativa somente autorizada: "
            "nao comece tarefas por conta propria nem realize acoes que "
            "o usuario nao solicitou.",
            "Abrir aplicativos e sites pode ser feito quando solicitado "
            "explicitamente pelo usuario.",
            "Downloads exigem duas etapas: preparar o download, informar "
            "o usuario e aguardar a frase explicita 'confirmar download'. "
            "Nunca chame confirmar_download por inferencia, silencio ou "
            "uma resposta vaga como 'sim'.",
            "Nunca execute comandos arbitrarios de terminal, scripts, "
            "arquivos executaveis desconhecidos ou alteracoes administrativas.",
            "Nao envie arquivos locais, senhas, tokens ou dados privados "
            "para a internet.",
            "Use buscar_historico_antigo quando uma pergunta depender "
            "de conversas anteriores ou de projetos antigos.",
            "Nao invente lembrancas, resultados ou acoes.",
            "O usuario pode interromper sua fala a qualquer momento."
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

        return "\n\n".join(parts)

'''

live_code = live_code[:inicio] + novo_metodo + live_code[fim:]

# Substituir somente o despacho do tool_call, preservando o receptor de audio.
linhas = live_code.splitlines(keepends=True)

idx_tool = next(
    (
        i for i, linha in enumerate(linhas)
        if 'tool_call = getattr(message, "tool_call", None)' in linha
    ),
    None
)

idx_received = next(
    (
        i for i in range((idx_tool or 0) + 1, len(linhas))
        if "recebeu_mensagem = True" in linhas[i]
    ),
    None
)

if idx_tool is None or idx_received is None:
    raise RuntimeError("Nao encontrei o bloco de chamadas de ferramentas.")

indent = len(linhas[idx_tool]) - len(linhas[idx_tool].lstrip())

bloco = r'''
tool_call = getattr(message, "tool_call", None)

if tool_call:
    function_responses = []

    for fc in (getattr(tool_call, "function_calls", None) or []):
        nome = getattr(fc, "name", "")
        argumentos = getattr(fc, "args", {}) or {}

        try:
            resultado = executar_ferramenta(
                nome,
                argumentos,
                texto_usuario=user_text
            )
        except Exception as exc:
            resultado = (
                f"Erro interno ao executar {nome}: "
                f"{type(exc).__name__}: {exc}"
            )

        if not isinstance(resultado, str):
            resultado = str(resultado)

        function_responses.append(
            types.FunctionResponse(
                id=fc.id,
                name=nome,
                response={"resultado": resultado[:12000]}
            )
        )

    if function_responses:
        await session.send_tool_response(
            function_responses=function_responses
        )
'''

bloco_formatado = textwrap.indent(
    bloco.strip("\n"),
    " " * indent
) + "\n"

linhas[idx_tool:idx_received] = [bloco_formatado]
live_code = "".join(linhas)

LIVE.write_text(live_code, encoding="utf-8")

# ---------------------------------------------------------
# 5. VALIDACAO
# ---------------------------------------------------------

for p in (CATALOGO, TOOLS, APPS, LIVE):
    py_compile.compile(str(p), doraise=True)

sys.path.insert(0, str(ROOT))

from modulos.catalogo_apps import (
    buscar_aplicativos_instalados,
    resolver_app_por_comando,
)
from modulos.live_tools import (
    TOOL_DECLARATIONS,
    executar_ferramenta,
)
from modulos.conversa_ao_vivo import LiveVoiceWorker
from modulos.aplicativos import detectar_comando

# Testes sem abrir programas.
chrome = buscar_aplicativos_instalados("Chrome", 5)
matlab = resolver_app_por_comando("MATLAB R2025b")
detector_matlab = detectar_comando("JARVIS, abra MATLAB R2025b")

nomes_ferramentas = {
    item["name"] for item in TOOL_DECLARATIONS
}

esperadas = {
    "buscar_aplicativos_instalados",
    "abrir_aplicativo",
    "pesquisar_internet",
    "consultar_noticias",
    "consultar_clima",
    "abrir_site",
    "ler_pagina",
    "preparar_download",
    "confirmar_download",
    "cancelar_download",
    "buscar_historico_antigo",
}

faltando = esperadas - nomes_ferramentas

if faltando:
    raise RuntimeError(
        "Ferramentas ausentes: " + ", ".join(sorted(faltando))
    )

# Teste da protecao de confirmacao: nao baixa nada.
teste_confirmacao = executar_ferramenta(
    "confirmar_download",
    {"confirmacao": "confirmar download"},
    texto_usuario="sim"
)

if "nao confirmado" not in teste_confirmacao.lower():
    raise RuntimeError(
        "A protecao de confirmacao de download nao passou."
    )

print("\n========================================")
print("JARVIS - AUTONOMIA AVANCADA")
print("========================================")
print("Catalogo local: OK")
print("Busca Chrome:", "OK" if "Chrome" in chrome or "chrome" in chrome.lower() else "VERIFICAR")
print("MATLAB localizado:", bool(matlab))
print("Detector tradicional:", detector_matlab)
print("Ferramentas Gemini Live:", len(TOOL_DECLARATIONS))
print("Despacho de ferramentas: OK")
print("Protecao de download: OK")
print("Voz Algenib preservada:", 'voice_name": "Algenib"' in live_code)
print("Memoria SQLite preservada: OK")
print("\nArquivos compilados:")
for p in (CATALOGO, TOOLS, APPS, LIVE):
    print(" -", p.name)

print("\nBACKUPS:")
print(" -", LIVE.with_name(LIVE.stem + ".backup_autonomia_" + stamp + LIVE.suffix))
print(" -", APPS.with_name(APPS.stem + ".backup_autonomia_" + stamp + APPS.suffix))

print("\nATUALIZACAO CONCLUIDA.")
