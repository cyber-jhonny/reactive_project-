import os
import sys
import wave
import time
import tempfile

import numpy as np
import sounddevice as sd

from scipy.io import wavfile
from piper import PiperVoice


BASE_DIR = getattr(
    sys,
    "_MEIPASS",
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

MODELO = os.path.join(
    BASE_DIR, "voz", "modelos", "pt_BR-faber-medium.onnx"
)

print("JARVIS: Carregando modelo de voz...")

VOICE = PiperVoice.load(MODELO)

print("JARVIS: Voz carregada e pronta!")


def falar(texto, on_audio_level=None):

    if not texto or not texto.strip():
        return

    caminho_audio = os.path.join(
        tempfile.gettempdir(),
        "jarvis_resposta.wav"
    )

    try:
        inicio = time.perf_counter()

        with wave.open(caminho_audio, "wb") as arquivo:
            VOICE.synthesize_wav(texto, arquivo)

        print(
            f"[PIPER] Geracao: "
            f"{time.perf_counter() - inicio:.2f}s"
        )

        taxa, audio = wavfile.read(caminho_audio)
        audio = np.asarray(audio)

        if audio.size == 0:
            return

        if np.issubdtype(audio.dtype, np.integer):
            info = np.iinfo(audio.dtype)
            escala = float(max(abs(info.min), info.max))
            audio = audio.astype(np.float32) / escala
        else:
            audio = audio.astype(np.float32)

        if audio.ndim == 1:
            audio = audio.reshape(-1, 1)
        elif audio.ndim > 2:
            audio = audio.reshape(audio.shape[0], -1)

        audio = np.ascontiguousarray(
            np.clip(audio, -1.0, 1.0),
            dtype=np.float32
        )

        inicio = time.perf_counter()
        tamanho_bloco = max(512, int(taxa * 0.04))

        try:
            with sd.OutputStream(
                samplerate=taxa,
                channels=audio.shape[1],
                dtype="float32"
            ) as stream:

                for posicao in range(0, len(audio), tamanho_bloco):
                    trecho = audio[
                        posicao:posicao + tamanho_bloco
                    ]

                    # Mede o volume do proprio audio de saida.
                    rms = float(
                        np.sqrt(
                            np.mean(trecho.astype(np.float64) ** 2)
                        )
                    )
                    pico = float(np.max(np.abs(trecho)))

                    nivel = min(
                        1.0,
                        max(rms * 5.5, pico * 0.42)
                    )

                    if on_audio_level is not None:
                        on_audio_level(nivel)

                    stream.write(trecho)

        finally:
            if on_audio_level is not None:
                on_audio_level(0.0)

        print(
            f"[PIPER] Reproducao: "
            f"{time.perf_counter() - inicio:.2f}s"
        )

    finally:
        if os.path.exists(caminho_audio):
            os.remove(caminho_audio)
