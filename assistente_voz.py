import sounddevice as sd
import numpy as np
import queue
import time

from collections import deque
from scipy.signal import resample_poly
from faster_whisper import WhisperModel

from modulos.inteligencia import conversar
from voz.falar import falar


# CONFIGURAÇÕES DE ÁUDIO
DISPOSITIVO = 1
FREQUENCIA = 44100
FREQUENCIA_WHISPER = 16000

BLOCO_MS = 30
BLOCO_AMOSTRAS = int(FREQUENCIA * BLOCO_MS / 1000)

LIMIAR_VOZ = 0.006
SILENCIO_FINAL = 0.9
TEMPO_MAXIMO = 30


print("JARVIS: Inicializando sistemas...")

modelo = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8"
)

print("JARVIS: Sistemas inicializados.")

falar("Olá! Estou pronto. Pode falar comigo.")


def capturar_fala():

    fila_audio = queue.Queue()

    def callback(indata, frames, time_info, status):
        fila_audio.put(indata.copy())

    pre_audio = deque(maxlen=8)
    audio_capturado = []

    voz_detectada = False
    contador_voz = 0
    contador_silencio = 0

    inicio_fala = None

    with sd.InputStream(
        device=DISPOSITIVO,
        samplerate=FREQUENCIA,
        channels=1,
        dtype="float32",
        blocksize=BLOCO_AMOSTRAS,
        callback=callback
    ):

        print("\nJARVIS: Aguardando sua voz...")

        while True:

            try:
                bloco = fila_audio.get(timeout=2)

            except queue.Empty:
                continue

            nivel = float(np.sqrt(np.mean(bloco ** 2)))

            # DETECTA O INÍCIO DA FALA
            if not voz_detectada:

                pre_audio.append(bloco)

                if nivel >= LIMIAR_VOZ:
                    contador_voz += 1
                else:
                    contador_voz = 0

                if contador_voz >= 2:

                    voz_detectada = True
                    inicio_fala = time.monotonic()

                    audio_capturado = list(pre_audio)

                    print("JARVIS: Estou ouvindo você...")

                continue

            # CONTINUA CAPTURANDO ENQUANTO HOUVER FALA
            audio_capturado.append(bloco)

            if nivel < LIMIAR_VOZ * 0.65:
                contador_silencio += 1
            else:
                contador_silencio = 0

            tempo_fala = time.monotonic() - inicio_fala

            # DETECTA O FINAL DA FALA
            blocos_silencio = int(
                SILENCIO_FINAL / (BLOCO_MS / 1000)
            )

            if contador_silencio >= blocos_silencio:
                print("JARVIS: Fala finalizada.")
                break

            # LIMITE DE SEGURANÇA
            if tempo_fala >= TEMPO_MAXIMO:
                print("JARVIS: Limite de gravação atingido.")
                break

    if not voz_detectada:
        return None

    audio = np.concatenate(audio_capturado).flatten()

    # CONVERTE PARA 16 KHZ, FORMATO DO WHISPER
    audio = resample_poly(
        audio,
        FREQUENCIA_WHISPER,
        FREQUENCIA
    ).astype(np.float32)

    return audio


print("\nJARVIS: Estou ouvindo. Diga sair para encerrar.")

try:

    while True:

        audio = capturar_fala()

        if audio is None:
            continue

        inicio_whisper = time.perf_counter()
        segmentos, info = modelo.transcribe(
            audio,
            language="pt",
            beam_size=5,
            vad_filter=False,
            condition_on_previous_text=False,
            initial_prompt=(
                "O nome do assistente ? JARVIS. "
                "O usu?rio fala portugu?s brasileiro informal, "
                "com express?es coloquiais da Bahia. "
                "Vocabul?rio: JARVIS, Lauro de Freitas, Salvador, Bahia, "
                "cara, v?i, velho, maluco, massa, oxente."
            )
        )

        texto = " ".join(
            segmento.text.strip()
            for segmento in segmentos
        ).strip()
        print(f"[TEMPO] Whisper: {time.perf_counter() - inicio_whisper:.2f}s")

        if not texto:
            continue

        print(f"\nVOCÊ: {texto}")

        if texto.lower().strip(" .,! ?") in [
            "sair",
            "encerrar",
            "desligar jarvis"
        ]:

            falar("Até mais! Encerrando meus sistemas.")
            break

        inicio_gemini = time.perf_counter()
        resposta = conversar(texto)
        print(f"[TEMPO] Gemini: {time.perf_counter() - inicio_gemini:.2f}s")

        print(f"\nJARVIS: {resposta}")

        inicio_piper = time.perf_counter()
        falar(resposta)
        print(f"[TEMPO] Piper: {time.perf_counter() - inicio_piper:.2f}s")

except KeyboardInterrupt:

    print("\nJARVIS: Encerrando sistema.")

except Exception as erro:

    print(f"\nERRO: {erro}")