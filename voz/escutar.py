
import sounddevice as sd
from faster_whisper import WhisperModel

DISPOSITIVO = 1
FREQUENCIA = 16000
DURACAO = 5

print("JARVIS: Inicializando reconhecimento de voz...")

modelo = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("JARVIS: Sistema pronto!")
print("JARVIS: Estou ouvindo. Fale quando quiser.")
print("JARVIS: Pressione Ctrl + C para encerrar.\n")

try:
    while True:
        audio = sd.rec(
            int(DURACAO * FREQUENCIA),
            samplerate=FREQUENCIA,
            channels=1,
            dtype="float32",
            device=DISPOSITIVO
        )

        sd.wait()

        audio = audio.flatten()

        if abs(audio).max() < 0.01:
            continue

        segmentos, info = modelo.transcribe(
            audio,
            language="pt",
            beam_size=5,
            vad_filter=True
        )

        texto = " ".join(
            segmento.text.strip()
            for segmento in segmentos
        )

        if texto:
            print(f"VOCÊ: {texto}")

except KeyboardInterrupt:
    print("\nJARVIS: Encerrando sistema de escuta.")
