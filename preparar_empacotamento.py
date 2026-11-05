from pathlib import Path
import shutil

voz = Path("voz/falar.py")
spec_original = Path("JARVIS-Desktop.spec")
spec_novo = Path("JARVIS-Desktop-Novo.spec")

modelo = Path("voz/modelos/pt_BR-faber-medium.onnx")
config_modelo = Path("voz/modelos/pt_BR-faber-medium.onnx.json")

if not modelo.is_file() or not config_modelo.is_file():
    raise SystemExit("ERRO: modelo de voz ou configuracao nao encontrada.")

s = voz.read_text(encoding="utf-8-sig")

caminho_antigo = 'MODELO = r"C:\\Jarvis\\voz\\modelos\\pt_BR-faber-medium.onnx"'

if caminho_antigo in s:
    if "import sys" not in s:
        s = s.replace("import os\n", "import os\nimport sys\n", 1)

    novo_caminho = '''BASE_DIR = getattr(
    sys,
    "_MEIPASS",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

MODELO = os.path.join(
    BASE_DIR, "voz", "modelos", "pt_BR-faber-medium.onnx"
)'''

    shutil.copy2(voz, "falar_backup_empacotamento.py")
    s = s.replace(caminho_antigo, novo_caminho, 1)
    voz.write_text(s, encoding="utf-8")

elif 'MODELO = os.path.join(' not in s:
    raise SystemExit("ERRO: nao reconheci o caminho atual do modelo.")

spec = spec_original.read_text(encoding="utf-8-sig")

if "pt_BR-faber-medium.onnx" not in spec:
    marcador = "\n\na = Analysis("
    if spec.count(marcador) != 1:
        raise SystemExit("ERRO: estrutura do arquivo spec inesperada.")

    dados = f'''
datas += [
    (r"{modelo.resolve().as_posix()}", "voz/modelos"),
    (r"{config_modelo.resolve().as_posix()}", "voz/modelos"),
]
'''
    spec = spec.replace(marcador, "\n" + dados + marcador, 1)

spec_novo.write_text(spec, encoding="utf-8")

print("PREPARACAO CONCLUIDA!")
print("Modelo de voz configurado.")
print("Arquivo JSON incluido.")
print("Configuracao original preservada.")
print("Novo arquivo: JARVIS-Desktop-Novo.spec")
