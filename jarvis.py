
import os
import json
from dotenv import load_dotenv
from google import genai
from modulos.caminhos import ENV_FILE

from modulos.memoria import (
    salvar_mensagem,
    salvar_memoria,
    consultar_memorias,
    esquecer_memoria,
    historico_recente,
    atualizar_memoria
)


# ==========================================
# CONFIGURAÇÃO
# ==========================================

load_dotenv(ENV_FILE)

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    raise SystemExit("ERRO: Chave do Gemini não encontrada.")

client = genai.Client(
    api_key=API_KEY,
    http_options={"timeout": 60000}
)

MODELOS = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.1-flash-lite-preview"
]

INSTRUCOES = """
Você é JARVIS, um assistente pessoal inteligente.

PERSONALIDADE:
- Fale sempre em português brasileiro.
- Seja educado, natural, elegante e objetivo.
- Ajude com tecnologia, estudos e tarefas do computador.
- Chame o usuário de Mateus quando apropriado.
- Nunca afirme que executou uma ação sem realmente executá-la.

MEMÓRIA:
- Utilize as memórias fornecidas para personalizar suas respostas.
- Não invente informações sobre o usuário.
- As memórias são informações persistentes armazenadas localmente.
"""


# ==========================================
# CONEXÃO COM GEMINI
# ==========================================

def consultar_gemini(mensagem):

    for modelo in MODELOS:

        try:
            print(f"[Conectando: {modelo}]", flush=True)

            resposta = client.models.generate_content(
                model=modelo,
                contents=mensagem
            )

            if resposta.text:
                return resposta.text

        except Exception as erro:

            print(
                f"[Modelo indisponível: {modelo}] "
                f"{str(erro)[:150]}",
                flush=True
            )

    return None


# ==========================================
# CONVERSAÇÃO
# ==========================================

def conversar(pergunta):

    mensagens = historico_recente(12)
    memorias = consultar_memorias(20)

    contexto = "\n".join(
        f"{role}: {content}"
        for role, content in mensagens
    )

    contexto_memorias = "\n".join(
        f"- [{kind}] {content}"
        for _, kind, content in memorias
    )

    mensagem = f"""
{INSTRUCOES}

MEMÓRIAS IMPORTANTES DO USUÁRIO:
{contexto_memorias or "Nenhuma memória cadastrada."}

HISTÓRICO RECENTE:
{contexto}

NOVA MENSAGEM DO USUÁRIO:
{pergunta}
"""

    resposta = consultar_gemini(mensagem)

    if resposta:
        return resposta

    return "Não consegui acessar nenhum dos meus modelos no momento."


# ==========================================
# INTELIGÊNCIA DE MEMÓRIA
# ==========================================

def analisar_memoria(pergunta):

    memorias = consultar_memorias(50)

    contexto_memorias = "\n".join(
        f"ID: {identificador} | Categoria: {tipo} | Conteúdo: {conteudo}"
        for identificador, tipo, conteudo in memorias
    )

    instrucao = f"""
Você é o sistema de organização de memórias do JARVIS.

Analise a mensagem do usuário e compare com as memórias existentes.

MENSAGEM NOVA:
{pergunta}

MEMÓRIAS EXISTENTES:
{contexto_memorias or "Nenhuma memória cadastrada."}

REGRAS:
- Considere apenas informações duradouras e explicitamente declaradas.
- Não invente nem deduza informações pessoais.
- Não sugira perguntas, hipóteses ou informações temporárias.
- Não memorize senhas, chaves ou informações financeiras sensíveis.
- Não memorize informações de saúde ou outros dados sensíveis.
- Se a informação já existir sem novidade, não sugira nada.
- Se trouxer uma atualização, use action="update".
- Se for uma informação nova, use action="create".
- Categorias permitidas: fact, preference, project.
- Preserve os detalhes importantes ao propor uma atualização.
- Nunca atualize uma memória sem ter certeza de que se refere à mesma informação.

Responda SOMENTE em JSON.

Sem sugestão:
{{"save": false}}

Nova memória:
{{"save": true, "action": "create", "kind": "project", "content": "Resumo da informação"}}

Atualização:
{{"save": true, "action": "update", "id": 2, "kind": "project", "content": "Resumo atualizado"}}
"""

    resposta = consultar_gemini(instrucao)

    if not resposta:
        return None

    try:

        inicio = resposta.find("{")
        fim = resposta.rfind("}") + 1

        if inicio < 0 or fim <= inicio:
            return None

        dados = json.loads(resposta[inicio:fim])

        if dados.get("save") is not True:
            return None

        acao = dados.get("action")
        tipo = dados.get("kind")
        conteudo = dados.get("content")

        if acao not in ["create", "update"]:
            return None

        if tipo not in ["fact", "preference", "project"]:
            return None

        if not isinstance(conteudo, str) or not conteudo.strip():
            return None

        if acao == "create":

            return {
                "action": "create",
                "kind": tipo,
                "content": conteudo.strip()
            }

        identificador = dados.get("id")

        if not isinstance(identificador, int):
            return None

        ids_ativos = [
            item[0]
            for item in memorias
        ]

        if identificador not in ids_ativos:
            return None

        return {
            "action": "update",
            "id": identificador,
            "kind": tipo,
            "content": conteudo.strip()
        }

    except (ValueError, TypeError, json.JSONDecodeError):

        return None


# ==========================================
# INICIALIZAÇÃO
# ==========================================

print("=" * 55)
print("                 J.A.R.V.I.S ONLINE")
print("          Inteligência artificial conectada")
print("                MEMÓRIA INTELIGENTE")
print("=" * 55)

print("\nCOMANDOS:")
print("memorize: informação")
print("minhas memorias")
print("esquecer: ID")
print("sair\n")


# ==========================================
# SISTEMA PRINCIPAL
# ==========================================

memoria_pendente = None

while True:

    pergunta = input("Você: ").strip()

    if not pergunta:
        continue

    comando = pergunta.lower()

    # --------------------------------------
    # CONFIRMAÇÃO DE MEMÓRIA
    # --------------------------------------

    if memoria_pendente:

        if comando in ["sim", "s", "confirmo", "pode salvar"]:

            acao = memoria_pendente["action"]
            tipo = memoria_pendente["kind"]
            conteudo = memoria_pendente["content"]

            if acao == "create":

                identificador, criada = salvar_memoria(
                    conteudo,
                    tipo
                )

                if criada:
                    print(
                        f"\nJARVIS: Nova memória salva! "
                        f"ID {identificador}, categoria {tipo}.\n"
                    )
                else:
                    print(
                        "\nJARVIS: Essa informação já estava salva.\n"
                    )

            elif acao == "update":

                identificador = memoria_pendente["id"]

                sucesso = atualizar_memoria(
                    identificador,
                    conteudo,
                    tipo
                )

                if sucesso:
                    print(
                        f"\nJARVIS: Memória ID {identificador} "
                        "atualizada com sucesso.\n"
                    )
                else:
                    print(
                        "\nJARVIS: Não consegui atualizar essa memória.\n"
                    )

            memoria_pendente = None
            continue

        if comando in [
            "não",
            "nao",
            "n",
            "não salvar",
            "nao salvar"
        ]:

            memoria_pendente = None

            print(
                "\nJARVIS: Certo. Não vou alterar suas memórias.\n"
            )

            continue

        print(
            "\nJARVIS: Preciso que confirme com 'sim' ou 'não'.\n"
        )

        continue

    # --------------------------------------
    # ENCERRAR
    # --------------------------------------

    if comando in ["sair", "encerrar", "desligar"]:

        print(
            "\nJARVIS: Até logo. Estarei aguardando."
        )

        break

    # --------------------------------------
    # SALVAR MANUALMENTE
    # --------------------------------------

    if comando.startswith("memorize:"):

        informacao = pergunta[len("memorize:"):].strip()

        if informacao:

            identificador, criada = salvar_memoria(
                informacao,
                "fact"
            )

            if criada:
                print(
                    "\nJARVIS: Informação armazenada com sucesso.\n"
                )
            else:
                print(
                    "\nJARVIS: Essa informação já estava salva.\n"
                )

        else:

            print(
                "\nJARVIS: Informe o que deseja guardar.\n"
            )

        continue

    # --------------------------------------
    # CONSULTAR MEMÓRIAS
    # --------------------------------------

    if comando == "minhas memorias":

        memorias = consultar_memorias()

        if not memorias:

            print(
                "\nJARVIS: Ainda não tenho memórias cadastradas.\n"
            )

        else:

            print(
                "\nJARVIS: Estas são minhas memórias:\n"
            )

            for identificador, tipo, conteudo in memorias:

                print(
                    f"[ID {identificador}] [{tipo}] {conteudo}"
                )

            print()

        continue

    # --------------------------------------
    # ESQUECER MEMÓRIA
    # --------------------------------------

    if comando.startswith("esquecer:"):

        identificador = pergunta[len("esquecer:"):].strip()

        try:

            sucesso = esquecer_memoria(
                int(identificador)
            )

            if sucesso:

                print(
                    "\nJARVIS: Memória desativada.\n"
                )

            else:

                print(
                    "\nJARVIS: Não encontrei uma memória ativa com esse ID.\n"
                )

        except ValueError:

            print(
                "\nJARVIS: Informe um ID numérico válido.\n"
            )

        continue

    # --------------------------------------
    # CONVERSA NORMAL
    # --------------------------------------

    salvar_mensagem("user", pergunta)

    print(
        "\nJARVIS está pensando...\n",
        flush=True
    )

    resposta = conversar(pergunta)

    print(
        f"JARVIS: {resposta}\n"
    )

    salvar_mensagem("assistant", resposta)

    # --------------------------------------
    # ANÁLISE AUTOMÁTICA DE MEMÓRIA
    # --------------------------------------

    print(
        "JARVIS está analisando se há algo importante para memorizar...\n"
    )

    sugestao = analisar_memoria(pergunta)

    if sugestao:

        memoria_pendente = sugestao

        tipo = sugestao["kind"]
        conteudo = sugestao["content"]

        if sugestao["action"] == "create":

            print(
                "JARVIS: Identifiquei uma nova informação "
                "que pode ser útil no futuro:"
            )

            print(f"'{conteudo}'")
            print(f"Categoria: {tipo}")

            print(
                "Deseja guardar essa nova memória? "
                "Responda sim ou não.\n"
            )

        elif sugestao["action"] == "update":

            identificador = sugestao["id"]

            print(
                "JARVIS: Identifiquei uma possível atualização "
                "de uma memória existente."
            )

            print(f"Memória ID: {identificador}")
            print(f"Nova informação: '{conteudo}'")
            print(f"Categoria: {tipo}")

            print(
                "Deseja atualizar essa memória? "
                "Responda sim ou não.\n"
            )
