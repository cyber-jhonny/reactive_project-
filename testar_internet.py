from modulos.internet import detectar_comando_internet

testes = [
    "JARVIS, pesquise na internet sobre a AMD",
    "Pesquise as últimas notícias sobre tecnologia",
    "Quais são as notícias sobre inteligência artificial?",
    "Qual é a previsão do tempo em Salvador",
    "Abra o YouTube",
    "Acesse github.com",
    "Resuma https://example.com",
    "Baixe https://example.com/documento.pdf"
]

for texto in testes:
    print(texto)
    print(" ->", detectar_comando_internet(texto))
    print()
