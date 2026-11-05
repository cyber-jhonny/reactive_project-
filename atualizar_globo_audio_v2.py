from pathlib import Path
import re
import shutil

interface = Path("interface.py")
voz = Path("voz/falar.py")

s = interface.read_text(encoding="utf-8-sig")

# Validar a estrutura original.
qtcore = "from PySide6.QtCore import Qt, QThread, Signal, QTimer"
qtgui = "from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient, QFont"
sinal = "    conversation_changed = Signal()"
conexao = "        self.worker.status.connect(self.update_status)"
chamada = "        falar(answer)"

padrao_classe = re.compile(
    r"^class CoreOrb\(QWidget\):\s*\n.*?(?=^class MainWindow\(QMainWindow\):)",
    re.MULTILINE | re.DOTALL
)

validacoes = [
    (s.count(qtcore) == 1, "Importacao QtCore nao encontrada."),
    (s.count(qtgui) == 1, "Importacao QtGui nao encontrada."),
    (s.count(sinal) == 1, "Sinal do worker nao encontrado."),
    (s.count(conexao) == 1, "Conexao do worker nao encontrada."),
    (s.count(chamada) == 1, "Chamada de voz nao encontrada."),
    (len(padrao_classe.findall(s)) == 1, "Classe CoreOrb nao encontrada na raiz.")
]

for ok, mensagem in validacoes:
    if not ok:
        raise SystemExit("CANCELADO: " + mensagem)

# Backups do estado restaurado.
shutil.copy2(interface, "interface_backup_globo_audio_v2.py")
shutil.copy2(voz, "falar_backup_globo_audio_v2.py")

# Importacoes corretas: QRectF e QPointF pertencem ao QtCore.
s = s.replace(
    qtcore,
    qtcore + ", QRectF, QPointF",
    1
)

s = s.replace(
    qtgui,
    qtgui + ", QPainterPath, QPolygonF",
    1
)

novo_globo = r'''class CoreOrb(QWidget):

    def __init__(self):
        super().__init__()

        self.phase = 0.0
        self.state = "STANDBY"
        self.audio_level = 0.0
        self.visual_level = 0.0

        self.setMinimumSize(300, 300)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)

    def animate(self):
        self.phase += 0.025

        diferenca = self.audio_level - self.visual_level
        velocidade = 0.42 if diferenca > 0 else 0.16
        self.visual_level += diferenca * velocidade

        if self.visual_level < 0.003:
            self.visual_level = 0.0

        self.update()

    def set_state(self, state):
        self.state = state
        self.update()

    def set_audio_level(self, level):
        try:
            self.audio_level = max(0.0, min(1.0, float(level)))
        except (ValueError, TypeError):
            self.audio_level = 0.0

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx = self.width() / 2
        cy = self.height() / 2
        radius = min(self.width(), self.height()) * 0.255
        level = self.visual_level

        # Aura holografica.
        glow = radius * (1.8 + level * 0.55)

        gradient = QRadialGradient(cx, cy, glow)
        gradient.setColorAt(
            0, QColor(20, 145, 255, int(35 + level * 95))
        )
        gradient.setColorAt(
            0.55, QColor(20, 110, 220, int(18 + level * 35))
        )
        gradient.setColorAt(1, QColor(5, 12, 25, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(
            QRectF(cx - glow, cy - glow, glow * 2, glow * 2)
        )

        # Ondas de expansao sincronizadas com a voz.
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if level > 0.015:
            for index in range(3):
                progresso = (
                    self.phase * 1.15 + index * 0.34
                ) % 1.0

                wave_radius = radius * (
                    1.16 + progresso * 0.58 + level * 0.12
                )

                alpha = int(
                    150 * level * (1 - progresso) *
                    (1 - index * 0.16)
                )

                painter.setPen(
                    QPen(QColor(65, 195, 255, max(0, alpha)), 1.5)
                )
                painter.drawEllipse(
                    QRectF(
                        cx - wave_radius,
                        cy - wave_radius,
                        wave_radius * 2,
                        wave_radius * 2
                    )
                )

        # Aneis orbitais.
        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-18)

        painter.setPen(QPen(QColor(45, 160, 235, 55), 1))
        painter.drawEllipse(
            QRectF(
                -radius * 1.48, -radius * 0.48,
                radius * 2.96, radius * 0.96
            )
        )

        painter.rotate(36)
        painter.setPen(QPen(QColor(55, 190, 255, 45), 1))
        painter.drawEllipse(
            QRectF(
                -radius * 1.38, -radius * 0.42,
                radius * 2.76, radius * 0.84
            )
        )
        painter.restore()

        # Raios externos que acompanham a amplitude.
        for index in range(72):
            angle = math.radians(
                index * 5 + self.phase * 12
            )

            variacao = 0.5 + 0.5 * math.sin(
                math.radians(index * 13) + self.phase * 5
            )

            r1 = radius * 1.07
            r2 = radius * (
                1.075 + level * (0.045 + variacao * 0.075)
            )

            painter.setPen(
                QPen(
                    QColor(90, 215, 255, int(35 + level * 170)),
                    1.3
                )
            )

            painter.drawLine(
                int(cx + math.cos(angle) * r1),
                int(cy + math.sin(angle) * r1),
                int(cx + math.cos(angle) * r2),
                int(cy + math.sin(angle) * r2)
            )

        # Superficie da Terra.
        esfera = QRectF(
            cx - radius, cy - radius,
            radius * 2, radius * 2
        )

        esfera_gradient = QRadialGradient(
            cx - radius * 0.32,
            cy - radius * 0.38,
            radius * 1.65
        )

        esfera_gradient.setColorAt(0, QColor("#164B78"))
        esfera_gradient.setColorAt(0.48, QColor("#092C50"))
        esfera_gradient.setColorAt(1, QColor("#031323"))

        painter.setBrush(esfera_gradient)
        painter.setPen(QPen(QColor("#66DFFF"), 2))
        painter.drawEllipse(esfera)

        # Recorte esferico para as linhas e continentes.
        clip = QPainterPath()
        clip.addEllipse(esfera)

        painter.save()
        painter.setClipPath(clip)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Latitudes.
        for latitude in (-0.70, -0.38, 0.0, 0.38, 0.70):
            largura = radius * math.sqrt(
                max(0.0, 1.0 - latitude * latitude)
            )
            altura = radius * 0.16 * (
                1 - abs(latitude) * 0.45
            )

            painter.setPen(
                QPen(QColor(64, 190, 255, 115), 1)
            )

            painter.drawEllipse(
                QRectF(
                    cx - largura,
                    cy + latitude * radius * 0.75 - altura,
                    largura * 2,
                    altura * 2
                )
            )

        # Longitudes em movimento.
        for index, deslocamento in enumerate((0.0, 2.1, 4.2)):
            fator = 0.16 + 0.78 * abs(
                math.cos(self.phase * 0.20 + deslocamento)
            )
            largura = radius * fator

            painter.setPen(
                QPen(QColor(65, 185, 255, 135), 1)
            )

            painter.drawEllipse(
                QRectF(
                    cx - largura, cy - radius,
                    largura * 2, radius * 2
                )
            )

        # Continentes estilizados.
        continentes = [
            [
                (-0.83, -0.53), (-0.64, -0.75),
                (-0.38, -0.69), (-0.28, -0.51),
                (-0.39, -0.30), (-0.56, -0.18),
                (-0.66, 0.02), (-0.82, -0.16)
            ],
            [
                (-0.34, 0.02), (-0.16, 0.06),
                (-0.10, 0.30), (-0.18, 0.57),
                (-0.29, 0.86), (-0.40, 0.58),
                (-0.45, 0.29)
            ],
            [
                (-0.08, -0.57), (0.15, -0.72),
                (0.43, -0.65), (0.76, -0.43),
                (0.83, -0.17), (0.61, -0.08),
                (0.47, 0.08), (0.20, -0.02),
                (0.04, -0.23)
            ],
            [
                (0.02, -0.04), (0.27, -0.11),
                (0.36, 0.14), (0.28, 0.48),
                (0.14, 0.73), (0.02, 0.48),
                (-0.08, 0.17)
            ],
            [
                (0.48, 0.43), (0.70, 0.34),
                (0.82, 0.50), (0.64, 0.69),
                (0.47, 0.58)
            ]
        ]

        painter.setPen(
            QPen(QColor(100, 225, 255, 185), 1)
        )
        painter.setBrush(
            QColor(42, 175, 230, int(90 + level * 65))
        )

        for pontos in continentes:
            poligono = QPolygonF([
                QPointF(cx + x * radius, cy + y * radius)
                for x, y in pontos
            ])
            painter.drawPolygon(poligono)

        painter.restore()

        # Contorno luminoso final.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                QColor(105, 225, 255, int(175 + level * 75)),
                2
            )
        )
        painter.drawEllipse(esfera)

        painter.end()


'''

# Substituir a classe inteira, incluindo o inicio da linha.
s, quantidade = padrao_classe.subn(
    lambda _: novo_globo + "\n\n",
    s,
    count=1
)

if quantidade != 1:
    raise SystemExit("Nao foi possivel substituir a classe CoreOrb.")

# Sinal de nivel de audio.
s = s.replace(
    sinal,
    sinal + "\n    audio_level = Signal(float)",
    1
)

# Reproducao da resposta principal.
s = s.replace(
    chamada,
    "        falar(answer, on_audio_level=self.audio_level.emit)",
    1
)

# Conexao do sinal com o globo.
s = s.replace(
    conexao,
    conexao + "\n"
    "        self.worker.audio_level.connect(self.orb.set_audio_level)",
    1
)

novo_voz = r'''import os
import wave
import time
import tempfile

import numpy as np
import sounddevice as sd

from scipy.io import wavfile
from piper import PiperVoice


MODELO = r"C:\Jarvis\voz\modelos\pt_BR-faber-medium.onnx"

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
'''

# Salvar somente depois de todas as verificacoes estruturais.
interface.write_text(s, encoding="utf-8")
voz.write_text(novo_voz, encoding="utf-8")

print("GLOBO HOLOGRAFICO ATUALIZADO!")
print("SINCRONIZACAO COM AUDIO DE SAIDA CONFIGURADA.")
print("Backups: interface_backup_globo_audio_v2.py")
print("         falar_backup_globo_audio_v2.py")
