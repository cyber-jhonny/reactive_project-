import sounddevice as sd
from scipy.io.wavfile import write
import numpy as np

dispositivo = 1
duracao = 5
frequencia = 16000

print("JARVIS: Pode falar! Gravando por 5 segundos...")

audio = sd.rec(
    int(duracao * frequencia),
    samplerate=frequencia,
    channels=1,
    dtype="int16",
    device=dispositivo
)

sd.wait()

write(r"C:\Jarvis\voz\teste_microfone.wav", frequencia, audio)

print("JARVIS: Gravação concluída!")
print("Arquivo salvo em C:\\Jarvis\\voz\\teste_microfone.wav")
