from faster_whisper import WhisperModel

arquivo = r"C:\Jarvis\voz\teste_microfone.wav"

print("JARVIS: Carregando meu sistema de reconhecimento de voz...")

modelo = WhisperModel(
    "base",
    device="cpu",
    compute_type="int8"
)

print("JARVIS: Analisando sua voz...")

segmentos, info = modelo.transcribe(
    arquivo,
    language="pt",
    beam_size=5
)

texto = " ".join(segmento.text.strip() for segmento in segmentos)

print("\nVocê disse:")
print(texto if texto else "Não consegui identificar nenhuma fala.")
