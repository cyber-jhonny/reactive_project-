
import os
import re
import time
import socket
import ipaddress
import subprocess
import unicodedata

from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin, unquote

import requests
from ddgs import DDGS

from modulos.caminhos import DOWNLOADS_DIR, CHROME_PATH

PASTA_DOWNLOADS = DOWNLOADS_DIR
LIMITE_DOWNLOAD = 25 * 1024 * 1024
TIMEOUT = 15

DOWNLOADS_PERMITIDOS = {
    ".pdf", ".txt", ".csv", ".png", ".jpg",
    ".jpeg", ".webp", ".mp3", ".wav", ".mp4"
}

SITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "twitch": "https://www.twitch.tv",
    "gmail": "https://mail.google.com",
    "github": "https://github.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "spotify": "https://open.spotify.com",
    "reddit": "https://www.reddit.com",
    "openai": "https://openai.com"
}

_DOWNLOAD_PENDENTE = None


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    texto = "".join(
        c for c in texto if not unicodedata.combining(c)
    )
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def localizar_url(texto):
    resultado = re.search(
        r"(https?://[^\s<>]+|www\.[^\s<>]+)",
        texto,
        re.IGNORECASE
    )

    if resultado:
        return resultado.group(1).rstrip(".,;:!?)]}")

    return None


def validar_url(url, verificar_dns=False):
    url = url.strip().rstrip(".,;:!?)]}")

    if not url.startswith(("https://", "http://")):
        url = "https://" + url

    partes = urlsplit(url)

    if partes.scheme != "https":
        raise ValueError("Somente conexões HTTPS são permitidas.")

    if not partes.hostname or partes.username or partes.password:
        raise ValueError("Endereço inválido.")

    host = partes.hostname.lower()

    if host == "localhost" or host.endswith(".local"):
        raise ValueError("Endereço local não permitido.")

    if partes.port not in (None, 443):
        raise ValueError("Porta não autorizada.")

    try:
        endereco = ipaddress.ip_address(host)
        if not endereco.is_global:
            raise ValueError("Endereço IP privado não permitido.")
    except ValueError as erro:
        if "não permitido" in str(erro):
            raise

        if verificar_dns:
            try:
                enderecos = socket.getaddrinfo(host, 443)
                ips = {
                    ipaddress.ip_address(item[4][0])
                    for item in enderecos
                }

                if not ips or not all(ip.is_global for ip in ips):
                    raise ValueError(
                        "O domínio aponta para endereço não público."
                    )
            except OSError:
                raise ValueError("Não foi possível validar o domínio.")

    return url


def detectar_comando_internet(texto):
    global _DOWNLOAD_PENDENTE

    original = texto.strip()
    frase = normalizar(original).strip(" .!?")

    # Confirmação e cancelamento de downloads.
    if frase in ("confirmar download", "confirmo download", "pode baixar"):
        return (
            {"acao": "confirmar_download"}
            if _DOWNLOAD_PENDENTE else None
        )

    if frase in ("cancelar download", "cancela download", "nao baixar"):
        return (
            {"acao": "cancelar_download"}
            if _DOWNLOAD_PENDENTE else None
        )

    # Solicitação de download.
    resultado = re.match(
        r"^(?:jarvis[, ]*)?(?:baixe|baixar|faca download de|"
        r"fazer download de)\s+(.+)$",
        original,
        re.IGNORECASE
    )

    if resultado:
        url = localizar_url(resultado.group(1))
        if url:
            return {"acao": "download", "url": url}

    # Leitura de páginas.
    if re.match(
        r"^(?:jarvis\s+)?(?:resuma|resumir|leia|ler|"
        r"explique|explicar)\s+",
        frase
    ):
        url = localizar_url(original)
        if url:
            return {"acao": "ler_pagina", "url": url}

    # Notícias.
    padrao = (
        r"^(?:jarvis\s+)?"
        r"(?:(?:quais\s+(?:sao\s+)?(?:as\s+)?)|"
        r"(?:(?:pesquise|busque|procure)\s+(?:as\s+)?))?"
        r"(?:as\s+)?(?:ultimas\s+)?noticias"
        r"(?:\s+(?:sobre|de|do|da|em))?\s*(.*)$"
    )

    resultado = re.match(padrao, frase)

    if resultado:
        consulta = resultado.group(1).strip() or "Brasil"
        consulta = re.sub(r"^(?:a|o|as|os)\s+", "", consulta)
        return {
            "acao": "noticias",
            "consulta": consulta or "Brasil"
        }

    # Clima.
    padrao = (
        r"^(?:jarvis\s+)?(?:(?:consulte|veja|pesquise)\s+)?"
        r"(?:(?:qual\s+e\s+)?(?:a\s+)?)?"
        r"(?:previsao do tempo|previsao do clima|clima|tempo)"
        r"(?:\s+(?:em|de|para|na cidade de)\s+(.+))?$"
    )

    resultado = re.match(padrao, frase)

    if resultado:
        return {
            "acao": "clima",
            "cidade": resultado.group(1) or "Salvador"
        }

    # Abertura de sites.
    resultado = re.match(
        r"^(?:jarvis[, ]*)?(?:abra|acesse|visite|entre no|entre em)"
        r"\s+(.+)$",
        original,
        re.IGNORECASE
    )

    if resultado:
        destino = resultado.group(1).strip().rstrip(".,!?;:")
        destino = re.sub(
            r"^(?:o|a|os|as)\s+(?:site\s+)?",
            "",
            destino,
            flags=re.IGNORECASE
        ).strip()

        chave = normalizar(destino).strip(" .!?")

        if chave in SITES:
            return {"acao": "abrir_site", "url": SITES[chave]}

        url = localizar_url(destino)

        if url:
            return {"acao": "abrir_site", "url": url}

        if re.fullmatch(
            r"(?:www\.)?[a-z0-9-]+(?:\.[a-z]{2,})+(?:/\S*)?",
            destino,
            re.IGNORECASE
        ):
            return {"acao": "abrir_site", "url": destino}

    # Pesquisa geral.
    padrao = (
        r"^(?:jarvis\s+)?(?:pesquise|pesquisa|pesquisar|"
        r"procure|buscar|busque)\s+"
        r"(?:(?:na internet|na web)\s+)?"
        r"(?:(?:por|sobre|o que e|quem e)\s+)?(.+)$"
    )

    resultado = re.match(padrao, frase)

    if resultado:
        consulta = resultado.group(1).strip()
        consulta = re.sub(r"^(?:a|o|as|os)\s+", "", consulta)

        if consulta:
            return {"acao": "pesquisar", "consulta": consulta}

    return None


def pesquisar(consulta):
    try:
        resultados = DDGS(timeout=TIMEOUT).text(
            consulta,
            region="br-pt",
            safesearch="moderate",
            max_results=5
        )

        if not resultados:
            return "Não encontrei resultados para essa pesquisa."

        linhas = [f"Resultados sobre {consulta}:"]

        for numero, item in enumerate(resultados[:5], 1):
            linhas.append(
                f"{numero}. {item.get('title', 'Sem título')}"
            )
            linhas.append(item.get("body", "")[:450])
            linhas.append("Fonte: " + item.get("href", ""))

        return "\n\n".join(linhas)

    except Exception as erro:
        print("[Internet/Pesquisa]", erro)
        return "Não consegui pesquisar agora. Verifique sua conexão."


def pesquisar_noticias(consulta):
    try:
        resultados = DDGS(timeout=TIMEOUT).news(
            consulta,
            region="br-pt",
            safesearch="moderate",
            timelimit="w",
            max_results=5
        )

        if not resultados:
            return "Não encontrei notícias recentes."

        linhas = [f"Notícias sobre {consulta}:"]

        for numero, item in enumerate(resultados[:5], 1):
            linhas.append(
                f"{numero}. {item.get('title', 'Sem título')}"
            )

            if item.get("source"):
                linhas.append("Veículo: " + item["source"])

            if item.get("date"):
                linhas.append("Data: " + str(item["date"]))

            if item.get("body"):
                linhas.append(item["body"][:350])

            if item.get("url"):
                linhas.append("Fonte: " + item["url"])

        return "\n\n".join(linhas)

    except Exception as erro:
        print("[Internet/Notícias]", erro)
        return "Não consegui consultar as notícias agora."


def consultar_clima(cidade):
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={
                "name": cidade,
                "count": 1,
                "language": "pt",
                "format": "json"
            },
            timeout=TIMEOUT
        )
        geo.raise_for_status()

        locais = geo.json().get("results", [])

        if not locais:
            return f"Não encontrei a cidade {cidade}."

        local = locais[0]

        resposta = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": local["latitude"],
                "longitude": local["longitude"],
                "current": (
                    "temperature_2m,relative_humidity_2m,"
                    "apparent_temperature,precipitation,"
                    "weather_code,wind_speed_10m"
                ),
                "daily": (
                    "temperature_2m_max,temperature_2m_min,"
                    "precipitation_probability_max"
                ),
                "forecast_days": 3,
                "timezone": "auto"
            },
            timeout=TIMEOUT
        )
        resposta.raise_for_status()

        dados = resposta.json()
        atual = dados.get("current", {})
        diaria = dados.get("daily", {})

        codigos = {
            0: "Céu limpo",
            1: "Predominantemente limpo",
            2: "Parcialmente nublado",
            3: "Nublado",
            45: "Neblina",
            48: "Neblina com gelo",
            51: "Garoa leve",
            53: "Garoa moderada",
            55: "Garoa intensa",
            61: "Chuva leve",
            63: "Chuva moderada",
            65: "Chuva forte",
            80: "Pancadas de chuva leves",
            81: "Pancadas de chuva moderadas",
            82: "Pancadas de chuva fortes",
            95: "Trovoadas",
            96: "Trovoadas com granizo",
            99: "Trovoadas fortes com granizo"
        }

        nome = local.get("name", cidade)
        regiao = local.get("admin1", "")
        descricao = codigos.get(
            atual.get("weather_code"), "Condição variável"
        )

        linhas = [
            f"Clima em {nome} {regiao}:",
            f"Temperatura: {atual.get('temperature_2m', 'N/D')} °C.",
            f"Sensação térmica: {atual.get('apparent_temperature', 'N/D')} °C.",
            f"Condição: {descricao}.",
            f"Umidade: {atual.get('relative_humidity_2m', 'N/D')}%.",
            f"Vento: {atual.get('wind_speed_10m', 'N/D')} km/h.",
            "",
            "Previsão:"
        ]

        for i, data in enumerate(diaria.get("time", [])[:3]):
            minima = diaria["temperature_2m_min"][i]
            maxima = diaria["temperature_2m_max"][i]
            chuva = diaria["precipitation_probability_max"][i]

            linhas.append(
                f"{data}: mínima {minima} °C, máxima {maxima} °C, "
                f"chance de chuva {chuva}%."
            )

        linhas.append("Dados: Open-Meteo.")
        return "\n".join(linhas)

    except Exception as erro:
        print("[Internet/Clima]", erro)
        return "Não consegui consultar o clima agora."


def abrir_site(url):
    try:
        url = validar_url(url)

        if CHROME_PATH.is_file():
            subprocess.Popen(
                [str(CHROME_PATH), url],
                shell=False
            )
        else:
            os.startfile(url)

        return f"Abrindo {url}."

    except Exception as erro:
        return f"Não consegui abrir o site: {erro}"


class ExtratorHTML(HTMLParser):

    def __init__(self):
        super().__init__()
        self.textos = []
        self.ignorar = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript", "svg"):
            self.ignorar += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self.ignorar = max(0, self.ignorar - 1)

    def handle_data(self, data):
        if not self.ignorar and data.strip():
            self.textos.append(data.strip())


def ler_pagina(url):
    try:
        url = validar_url(url, verificar_dns=True)

        resposta = requests.get(
            url,
            timeout=TIMEOUT,
            allow_redirects=False,
            headers={"User-Agent": "Mozilla/5.0 JARVIS/1.0"}
        )

        if resposta.is_redirect:
            resposta.close()
            return "O site redirecionou a página. Acesse pelo Chrome."

        resposta.raise_for_status()

        if len(resposta.content) > 2 * 1024 * 1024:
            resposta.close()
            return "A página ultrapassa o limite de leitura."

        parser = ExtratorHTML()
        parser.feed(resposta.text)
        texto = " ".join(parser.textos)
        resposta.close()

        if not texto:
            return "Não consegui extrair texto dessa página."

        return f"Conteúdo de {url}:\n\n{texto[:4000]}"

    except Exception as erro:
        print("[Internet/Página]", erro)
        return "Não consegui ler essa página."


def preparar_download(url):
    global _DOWNLOAD_PENDENTE

    try:
        url = validar_url(url)
        nome = Path(unquote(urlsplit(url).path)).name
        extensao = Path(nome).suffix.lower()

        if not nome or extensao not in DOWNLOADS_PERMITIDOS:
            return (
                "Tipo de arquivo não autorizado. "
                "Aceito PDF, TXT, CSV, imagens, áudio e MP4."
            )

        _DOWNLOAD_PENDENTE = {
            "url": url,
            "nome": nome,
            "hora": time.monotonic()
        }

        return (
            f"Download preparado: {nome}. "
            "Destino: pasta downloads do projeto. "
            "Limite: 25 MB. Diga confirmar download para autorizar "
            "ou cancelar download para desistir."
        )

    except Exception as erro:
        return f"Não consegui preparar o download: {erro}"


def cancelar_download():
    global _DOWNLOAD_PENDENTE

    if not _DOWNLOAD_PENDENTE:
        return "Não existe download pendente."

    _DOWNLOAD_PENDENTE = None
    return "Download cancelado."


def confirmar_download():
    global _DOWNLOAD_PENDENTE

    if not _DOWNLOAD_PENDENTE:
        return "Não existe download pendente."

    pendente = _DOWNLOAD_PENDENTE
    _DOWNLOAD_PENDENTE = None

    if time.monotonic() - pendente["hora"] > 300:
        return "A confirmação expirou. Solicite novamente."

    resposta = None
    temporario = None

    try:
        url = validar_url(pendente["url"], verificar_dns=True)
        PASTA_DOWNLOADS.mkdir(parents=True, exist_ok=True)

        resposta = requests.get(
            url,
            stream=True,
            timeout=TIMEOUT,
            allow_redirects=False,
            headers={"User-Agent": "JARVIS/1.0"}
        )

        if resposta.is_redirect:
            destino = resposta.headers.get("Location", "")
            resposta.close()
            resposta = None

            if not destino:
                return "Redirecionamento sem destino informado."

            destino = validar_url(
                urljoin(url, destino),
                verificar_dns=True
            )

            resposta = requests.get(
                destino,
                stream=True,
                timeout=TIMEOUT,
                allow_redirects=False,
                headers={"User-Agent": "JARVIS/1.0"}
            )

            if resposta.is_redirect:
                return "Redirecionamento adicional não autorizado."

        resposta.raise_for_status()

        tamanho = resposta.headers.get("Content-Length")

        if tamanho and int(tamanho) > LIMITE_DOWNLOAD:
            return "Arquivo maior que o limite de 25 MB."

        nome = Path(pendente["nome"]).name
        destino = PASTA_DOWNLOADS / nome

        base = destino.stem
        extensao = destino.suffix
        contador = 1

        while destino.exists():
            destino = PASTA_DOWNLOADS / (
                f"{base}_{contador}{extensao}"
            )
            contador += 1

        temporario = destino.with_name(destino.name + ".part")
        total = 0

        with open(temporario, "wb") as arquivo:
            for bloco in resposta.iter_content(65536):
                if not bloco:
                    continue

                total += len(bloco)

                if total > LIMITE_DOWNLOAD:
                    raise ValueError("Limite de 25 MB excedido.")

                arquivo.write(bloco)

        temporario.replace(destino)
        temporario = None

        return (
            f"Download concluído: {destino}. "
            "O arquivo não foi executado."
        )

    except Exception as erro:
        print("[Internet/Download]", erro)
        return "O download falhou ou foi bloqueado."

    finally:
        if resposta is not None:
            resposta.close()

        if temporario is not None:
            temporario.unlink(missing_ok=True)


def executar_comando_internet(comando):
    acao = comando.get("acao")

    if acao == "pesquisar":
        return pesquisar(comando["consulta"])

    if acao == "noticias":
        return pesquisar_noticias(comando["consulta"])

    if acao == "clima":
        return consultar_clima(comando["cidade"])

    if acao == "abrir_site":
        return abrir_site(comando["url"])

    if acao == "ler_pagina":
        return ler_pagina(comando["url"])

    if acao == "download":
        return preparar_download(comando["url"])

    if acao == "confirmar_download":
        return confirmar_download()

    if acao == "cancelar_download":
        return cancelar_download()

    return "Não reconheci essa operação."
