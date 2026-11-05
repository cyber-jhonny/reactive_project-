from pathlib import Path
import shutil

interface = Path("interface.py")
voz = Path("voz/falar.py")

s = interface.read_text(encoding="utf-8-sig")

# Validar todos os pontos antes de alterar qualquer arquivo.
import_antigo = "from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient, QFont"
sinal_antigo = "    conversation_changed = Signal()"
status_connect = "        self.worker.status.connect(self.update_status)"
falar_saida = '            falar("Até mais! Encerrando meus sistemas.")'
falar_resposta = "        falar(answer)"

inicio = s.find("class CoreOrb(QWidget):")
fim = s.find("class MainWindow(QMainWindow):", inicio)

checks = [
    (s.count(import_antigo) == 1, "Importação Qt não encontrada."),
    (s.count(sinal_antigo) == 1, "Local do sinal não encontrado."),
    (s.count(status_connect) == 1, "Conexão do worker não encontrada."),
    (s.count(falar_saida) == 1, "Chamada de despedida não encontrada."),
    (s.count(falar_resposta) == 1, "Chamada de resposta não encontrada."),
    (inicio >= 0 and fim > inicio, "Classe CoreOrb não encontrada.")
]

for ok, mensagem in checks:
    if not ok:
        raise SystemExit("ALTERAÇÃO CANCELADA: " + mensagem)

# Backup dos arquivos originais.
shutil.copy2(interface, "interface_backup_globo_audio.py")
shutil.copy2(voz, "falar_backup_globo_audio.py")

novo_import = (
    "from PySide6.QtGui import QColor, QPainter, QPen, "
    "QRadialGradient, QFont, QPainterPath, QPolygonF, "
    "QPointF, QRectF"
)
s = s.replace(import_antigo, novo_import, 1)

novo_globo = r'''class CoreOrb(QWidget):

    def __init__(self):
        super().__init__()

        self.phase = 0.0
        self.state = "STANDBY"

        # Nível recebido exclusivamente da reprodução de voz do JARVIS.
        self.audio_level = 0.0
        self.visual_level = 0.0

        self.setMinimumSize(300, 300)

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(30)

    def animate(self):
        self.phase += 0.025

        # Suaviza as variações reais do áudio.
        self.visual_level += (
            self.audio_level - self.visual_level
        ) * (0.42 if self.audio_level > self.visual_level else 0.16)

        if self.visual_level < 0.003:
            self.visual_level = 0.0

        self.update()

    def set_state(self, state):
        self.state = state
        self.update()

    def set_audio_level(self, level):
        try:
            self.audio_level = max(0.0, min(1.0, float(level)))
        except (TypeError, ValueError):
            self.audio_level = 0.0

    def paintEvent(self, event):

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        cx = width / 2
        cy = height / 2

        level = self.visual_level
        radius = min(width, height) * 0.255

        azul = QColor(43, 190, 255)
        ciano = QColor(112, 232, 255)

        # Aura externa, com intensidade controlada pelo áudio.
        glow_radius = radius * (1.75 + level * 0.55)

        gradient = QRadialGradient(cx, cy, glow_radius)
        gradient.setColorAt(
            0,
            QColor(20, 145, 255, int(35 + level * 95))
        )
        gradient.setColorAt(
            0.55,
            QColor(20, 110, 220, int(18 + level * 35))
        )
        gradient.setColorAt(1, QColor(5, 12, 25, 0))

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(
            QRectF(
                cx - glow_radius,
                cy - glow_radius,
                glow_radius * 2,
                glow_radius * 2
            )
        )

        # Órbitas holográficas permanentes.
        painter.setBrush(Qt.BrushStyle.NoBrush)

        painter.save()
        painter.translate(cx, cy)
        painter.rotate(-18)

        painter.setPen(QPen(QColor(45, 160, 235, 45), 1))
        painter.drawEllipse(
            QRectF(-radius * 1.48, -radius * 0.48,
                   radius * 2.96, radius * 0.96)
        )

        painter.rotate(36)
        painter.setPen(QPen(QColor(55, 190, 255, 35), 1))
        painter.drawEllipse(
            QRectF(-radius * 1.38, -radius * 0.42,
                   radius * 2.76, radius * 0.84)
        )
        painter.restore()

        # Ondas circulares: só aparecem com áudio de saída.
        if level > 0.015:
            for index in range(3):
                deslocamento = (
                    self.phase * 1.15 + index * 0.34
                ) % 1.0

                wave_radius = radius * (
                    1.16 + deslocamento * 0.58 + level * 0.12
                )

                alpha = int(
                    150 * level * (1.0 - deslocamento) *
                    (1.0 - index * 0.16)
                )

                wave_color = QColor(65, 195, 255, max(0, alpha))
                wave_pen = QPen(wave_color, 1.5)
                painter.setPen(wave_pen)

                painter.drawEllipse(
                    QRectF(
                        cx - wave_radius,
                        cy - wave_radius,
                        wave_radius * 2,
                        wave_radius * 2
                    )
                )

        # Pequenos traços radiais que reagem à intensidade da voz.
        for index in range(72):
            angle = index * 5.0 + self.phase * 12
            rad = math.radians(angle)

            variacao = (
                0.5 + 0.5 * math.sin(
                    math.radians(index * 13) + self.phase * 5
                )
            )

            comprimento = level * (
                0.045 + variacao * 0.075
            )

            r1 = radius * 1.07
            r2 = radius * (1.075 + comprimento)

            alpha = int(35 + level * 170)
            painter.setPen(
                QPen(QColor(90, 215, 255, alpha), 1.3)
            )

            painter.drawLine(
                int(cx + math.cos(rad) * r1),
                int(cy + math.sin(rad) * r1),
                int(cx + math.cos(rad) * r2),
                int(cy + math.sin(rad) * r2)
            )

        # Esfera terrestre.
        sphere = QRectF(
            cx - radius,
            cy - radius,
            radius * 2,
            radius * 2
        )

        sphere_gradient = QRadialGradient(
            cx - radius * 0.32,
            cy - radius * 0.38,
            radius * 1.65
        )
        sphere_gradient.setColorAt(0, QColor("#164B78"))
        sphere_gradient.setColorAt(0.48, QColor("#092C50"))
        sphere_gradient.setColorAt(1, QColor("#031323"))

        painter.setBrush(sphere_gradient)
        painter.setPen(QPen(QColor("#66DFFF"), 2))
        painter.drawEllipse(sphere)

        # Tudo abaixo fica recortado dentro da esfera.
        clip = QPainterPath()
        clip.addEllipse(sphere)

        painter.save()
        painter.setClipPath(clip)

        # Linhas de latitude.
        painter.setBrush(Qt.BrushStyle.NoBrush)

        for latitude in (-0.70, -0.38, 0.0, 0.38, 0.70):
            largura = radius * math.sqrt(
                max(0.0, 1.0 - latitude * latitude)
            )
            altura = radius * 0.16 * (
                1.0 - abs(latitude) * 0.45
            )

            painter.setPen(
                QPen(QColor(64, 190, 255, 105), 1)
            )

            painter.drawEllipse(
                QRectF(
                    cx - largura,
                    cy + latitude * radius * 0.75 - altura,
                    largura * 2,
                    altura * 2
                )
            )

        # Linhas de longitude: movimento lento de rotação.
        for index, offset in enumerate((0.0, 2.1, 4.2)):
            fator = 0.16 + 0.78 * abs(
                math.cos(self.phase * 0.20 + offset)
            )
            largura = radius * fator

            painter.setPen(
                QPen(QColor(65, 185, 255, 115), 1)
            )

            painter.drawEllipse(
                QRectF(
                    cx - largura,
                    cy - radius,
                    largura * 2,
                    radius * 2
                )
            )

        # Continentes estilizados em azul luminoso.
        painter.setPen(QPen(QColor(100, 225, 255, 170), 1))
        painter.setBrush(QColor(42, 175, 230, 105))

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

        for pontos in continentes:
            poligono = QPolygonF([
                QPointF(
                    cx + x * radius,
                    cy + y * radius
                )
                for x, y in pontos
            ])
            painter.drawPolygon(poligono)

        # Contorno e brilho da esfera.
        painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(
            QPen(
                QColor(105, 225, 255, int(175 + level * 75)),
                2
            )
        )
        painter.drawEllipse(sphere)

        # Pequeno brilho de superfície.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(170, 245, 255, 75))
        painter.drawEllipse(
            QRectF(
                cx - radius * 0.52,
                cy - radius * 0.67,
                radius * 0.20,
                radius * 0.09
            )
        )

        painter.end()


'''

s = s[:inicio] + novo_globo + "\n\n" + s[fim:]

# Adicionar o sinal de nível de áudio.
s = s.replace(
    sinal_antigo,
    sinal_antigo + "\n    audio_level = Signal(float)",
    1
)

# Enviar o nível de áudio durante as duas falas do worker.
s = s.replace(
    falar_saida,
    '            falar("Até mais! Encerrando meus sistemas.", '
    'on_audio_level=self.audio_level.emit)',
    1
)

s = s.replace(
    falar_resposta,
    "        falar(answer, on_audio_level=self.audio_level.emit)",
    1
)

# Ligar o sinal à animação do globo.
s = s.replace(
    status_connect,
    status_connect + "\n"
    "        self.worker.audio_level.connect(self.orb.set_audio_level)",
    1
)

novo_arquivo_voz = r'''import os
import wave
import time
import tempfile
import threading

import numpy as np
import sounddevice as sd

from scipy.io import wavfile
from piper import PiperVoice


MODELO = r"C:\Jarvis\voz\modelos\pt_BR-faber-medium.onnx"

print("JARVIS: Carregando modelo de voz...")

# Mantém o modelo carregado para evitar atrasos a cada resposta.
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

        # Converte o áudio para float32, formato do OutputStream.
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

        posicao = 0
        finalizado = threading.Event()

        def audio_callback(outdata, frames, time_info, status):

            nonlocal posicao

            fim = min(posicao + frames, len(audio))
            trecho = audio[posicao:fim]

            outdata.fill(0)

            if len(trecho):
                outdata[:len(trecho)] = trecho

                # Mede a intensidade do áudio que está saindo.
                rms = float(
                    np.sqrt(np.mean(trecho.astype(np.float64) ** 2))
                )
                pico = float(np.max(np.abs(trecho)))

                nivel = min(
                    1.0,
                    max(rms * 5.5, pico * 0.42)
                )

                if on_audio_level is not None:
                    on_audio_level(nivel)

            posicao = fim

            if posicao >= len(audio):
                finalizado.set()
                raise sd.CallbackStop

        inicio = time.perf_counter()

        try:
            with sd.OutputStream(
                samplerate=taxa,
                channels=audio.shape[1],
                dtype="float32",
                callback=audio_callback,
                blocksize=0
            ):
                while not finalizado.wait(0.05):
                    pass

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

# Salvar as alterações.
interface.write_text(s, encoding="utf-8")
voz.write_text(novo_arquivo_voz, encoding="utf-8")

print("GLOBO HOLOGRAFICO E SINCRONIZACAO DE AUDIO ATUALIZADOS!")
print("Backups criados:")
print(" - interface_backup_globo_audio.py")
print(" - falar_backup_globo_audio.py")
