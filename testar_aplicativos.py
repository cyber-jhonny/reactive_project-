from modulos.aplicativos import detectar_comando, verificar_aplicativos

testes = [
    "JARVIS, abra o Discord",
    "Abra o OBS Studio",
    "Inicie o FiveM",
    "Abra o Spotify",
    "Abra o Discord e depois o Chrome",
    "Abra o Explorador de Arquivos"
]

print("=== TESTE DE RECONHECIMENTO ===")

for texto in testes:
    print(texto, "->", detectar_comando(texto))

print("\n=== APLICATIVOS DISPONIVEIS ===")

for chave, dados in verificar_aplicativos().items():
    print(dados["nome"], "->", "OK" if dados["disponivel"] else "NAO ENCONTRADO")
