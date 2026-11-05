
import os
import shutil
from pathlib import Path

# Diretório principal do projeto JARVIS
BASE_DIR = Path(__file__).resolve().parent.parent

# Arquivos e diretórios principais
ENV_FILE = BASE_DIR / ".env"
DATABASE_PATH = BASE_DIR / "memoria.db"
DATA_DIR = BASE_DIR / "dados"
CATALOG_PATH = DATA_DIR / "catalogo_aplicativos.json"
DOWNLOADS_DIR = BASE_DIR / "downloads"

# Modelos de voz
VOICE_MODELS_DIR = BASE_DIR / "voz" / "modelos"
PIPER_MODEL = VOICE_MODELS_DIR / "pt_BR-faber-medium.onnx"
PIPER_CONFIG = VOICE_MODELS_DIR / "pt_BR-faber-medium.onnx.json"


# Localização automática de programas
def localizar_executavel(*candidatos):
    for candidato in candidatos:
        if not candidato:
            continue

        caminho = Path(candidato).expanduser()

        if caminho.is_file():
            return caminho

        encontrado = shutil.which(caminho.name)
        if encontrado:
            return Path(encontrado)

    return Path("")


# Chrome
CHROME_PATH = localizar_executavel(
    os.path.join(
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        "Google", "Chrome", "Application", "chrome.exe"
    ),
    os.path.join(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        "Google", "Chrome", "Application", "chrome.exe"
    ),
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Google", "Chrome", "Application", "chrome.exe"
    ),
    "chrome.exe"
)


# OBS Studio
OBS_PATH = localizar_executavel(
    os.path.join(
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        "obs-studio", "bin", "64bit", "obs64.exe"
    ),
    os.path.join(
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        "obs-studio", "bin", "64bit", "obs64.exe"
    ),
    os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        "Programs", "obs-studio", "bin", "64bit", "obs64.exe"
    ),
    "obs64.exe"
)


# Steam: procura primeiro no Registro do Windows
def localizar_steam():
    candidatos = []

    try:
        import winreg

        registros = [
            (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam", "SteamPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam", "InstallPath"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam", "InstallPath"),
        ]

        for raiz, chave, valor in registros:
            try:
                with winreg.OpenKey(raiz, chave) as registro:
                    pasta, _ = winreg.QueryValueEx(registro, valor)
                    candidatos.append(
                        os.path.join(os.path.expandvars(pasta), "steam.exe")
                    )
            except OSError:
                continue

    except ImportError:
        pass

    candidatos.extend([
        os.path.join(
            os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
            "Steam", "steam.exe"
        ),
        os.path.join(
            os.environ.get("ProgramFiles", r"C:\Program Files"),
            "Steam", "steam.exe"
        ),
        "steam.exe"
    ])

    return localizar_executavel(*candidatos)


STEAM_PATH = localizar_steam()
