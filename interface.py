import sys
import math
import time
import queue
import threading
import traceback
from collections import deque

import numpy as np
import sounddevice as sd

from scipy.signal import resample_poly
from faster_whisper import WhisperModel

from PySide6.QtCore import Qt, QThread, Signal, QTimer, QRectF, QPointF
from PySide6.QtGui import QColor, QPainter, QPen, QRadialGradient, QFont, QPainterPath, QPolygonF
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout,
    QScrollArea, QSizePolicy, QListWidget, QListWidgetItem,
    QInputDialog, QMessageBox
)

from modulos.inteligencia import conversar
from modulos.aplicativos import detectar_comando, abrir_aplicativos
from modulos.internet import detectar_comando_internet, executar_comando_internet
from modulos.memoria import salvar_mensagem
from modulos.memoria import (
    criar_conversa, listar_conversas, obter_mensagens_conversa,
    renomear_conversa, excluir_conversa
)
from voz.falar import falar


# CONFIGURACAO
DISPOSITIVO = 1
FREQUENCIA = 44100
FREQUENCIA_WHISPER = 16000

BLOCO_MS = 30
BLOCO_AMOSTRAS = int(FREQUENCIA * BLOCO_MS / 1000)

LIMIAR_VOZ = 0.006
SILENCIO_FINAL = 0.9
TEMPO_MAXIMO = 30


class JarvisWorker(QThread):

    status = Signal(str)
    transcription = Signal(str)
    response = Signal(str)
    metrics = Signal(str)
    error = Signal(str)
    conversation_changed = Signal()
    audio_level = Signal(float)

    def __init__(self):
        super().__init__()

        self.stop_event = threading.Event()
        self.mic_enabled = threading.Event()
        self.mic_enabled.set()

        self.text_queue = queue.Queue()
        self.modelo = None
        self.conversation_id = None
        self.conversation_lock = threading.Lock()

    def stop(self):
        self.stop_event.set()

    def submit_text(self, text):
        if text.strip():
            self.text_queue.put(text.strip())

    def set_conversation(self, conversation_id):
        with self.conversation_lock:
            self.conversation_id = conversation_id

    def get_conversation(self):
        with self.conversation_lock:
            return self.conversation_id

    def set_microphone(self, enabled):
        if enabled:
            self.mic_enabled.set()
            self.status.emit("MICROFONE ATIVO")
        else:
            self.mic_enabled.clear()
            self.status.emit("MICROFONE PAUSADO")

    def capture_speech(self):

        audio_queue = queue.Queue()

        def callback(indata, frames, time_info, status):
            audio_queue.put(indata.copy())

        pre_audio = deque(maxlen=8)
        audio_captured = []

        voice_detected = False
        voice_count = 0
        silence_count = 0
        start_time = None

        silence_blocks = int(
            SILENCIO_FINAL / (BLOCO_MS / 1000)
        )

        with sd.InputStream(
            device=DISPOSITIVO,
            samplerate=FREQUENCIA,
            channels=1,
            dtype="float32",
            blocksize=BLOCO_AMOSTRAS,
            callback=callback
        ):

            self.status.emit("AGUARDANDO SUA VOZ")

            while not self.stop_event.is_set():

                if not self.mic_enabled.is_set():
                    return None

                try:
                    manual_text = self.text_queue.get_nowait()
                    return ("text", manual_text)
                except queue.Empty:
                    pass

                try:
                    block = audio_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                level = float(np.sqrt(np.mean(block ** 2)))

                if not voice_detected:

                    pre_audio.append(block)

                    if level >= LIMIAR_VOZ:
                        voice_count += 1
                    else:
                        voice_count = 0

                    if voice_count >= 2:
                        voice_detected = True
                        start_time = time.monotonic()
                        audio_captured = list(pre_audio)
                        self.status.emit("OUVINDO VOCE")

                    continue

                audio_captured.append(block)

                if level < LIMIAR_VOZ * 0.65:
                    silence_count += 1
                else:
                    silence_count = 0

                elapsed = time.monotonic() - start_time

                if silence_count >= silence_blocks:
                    self.status.emit("PROCESSANDO AUDIO")
                    break

                if elapsed >= TEMPO_MAXIMO:
                    break

        if not voice_detected:
            return None

        audio = np.concatenate(audio_captured).flatten()

        audio = resample_poly(
            audio,
            FREQUENCIA_WHISPER,
            FREQUENCIA
        ).astype(np.float32)

        return ("audio", audio)

    def process_message(self, text, whisper_time=0):

        text = text.strip()

        if not text:
            return

        self.transcription.emit(text)

        if text.lower().strip(" .,! ?") in [
            "sair",
            "encerrar",
            "desligar jarvis"
        ]:
            self.status.emit("ENCERRANDO")
            self.response.emit("Até mais! Encerrando meus sistemas.")
            falar("Até mais! Encerrando meus sistemas.")
            self.stop_event.set()
            return

        comandos_app = detectar_comando(text)

        if comandos_app:
            resultado = abrir_aplicativos(comandos_app)

            conversation_id = self.get_conversation()
            salvar_mensagem("user", text, conversation_id)
            salvar_mensagem("assistant", resultado, conversation_id)

            self.conversation_changed.emit()
            self.response.emit(resultado)

            self.status.emit("FALANDO")
            falar(resultado, on_audio_level=self.audio_level.emit)
            self.status.emit("SISTEMA ONLINE")
            return

        self.status.emit("PENSANDO...")

        start_gemini = time.perf_counter()
        conversation_id = self.get_conversation()
        answer = conversar(text, conversation_id)
        self.conversation_changed.emit()
        gemini_time = time.perf_counter() - start_gemini

        self.response.emit(answer)

        self.status.emit("FALANDO")

        start_voice = time.perf_counter()
        falar(answer, on_audio_level=self.audio_level.emit)
        voice_time = time.perf_counter() - start_voice

        self.metrics.emit(
            f"WHISPER {whisper_time:.2f}s  |  "
            f"GEMINI {gemini_time:.2f}s  |  "
            f"VOZ {voice_time:.2f}s"
        )

        self.status.emit("SISTEMA ONLINE")

    def run(self):

        try:
            self.status.emit("CARREGANDO WHISPER")

            self.modelo = WhisperModel(
                "small",
                device="cpu",
                compute_type="int8"
            )

            self.status.emit("SISTEMA ONLINE")

            while not self.stop_event.is_set():

                try:
                    manual_text = self.text_queue.get_nowait()
                    self.process_message(manual_text)
                    continue
                except queue.Empty:
                    pass

                if not self.mic_enabled.is_set():
                    self.status.emit("MICROFONE PAUSADO")
                    self.stop_event.wait(0.15)
                    continue

                captured = self.capture_speech()

                if captured is None:
                    continue

                kind, content = captured

                if kind == "text":
                    self.process_message(content)
                    continue

                self.status.emit("RECONHECENDO VOZ")

                start_whisper = time.perf_counter()

                segments, info = self.modelo.transcribe(
                    content,
                    language="pt",
                    beam_size=5,
                    vad_filter=False,
                    condition_on_previous_text=False,
                    initial_prompt=(
                        "O nome do assistente é JARVIS. "
                        "O usuário fala português brasileiro informal, "
                        "com expressões coloquiais da Bahia. "
                        "Vocabulário: JARVIS, Lauro de Freitas, Salvador, "
                        "Bahia, cara, véi, velho, maluco, massa, oxente."
                    )
                )

                text = " ".join(
                    segment.text.strip()
                    for segment in segments
                ).strip()

                whisper_time = time.perf_counter() - start_whisper

                if text:
                    self.process_message(text, whisper_time)

        except Exception as exc:
            traceback.print_exc()
            self.error.emit(str(exc))
            self.status.emit("ERRO NO SISTEMA")

        finally:
            self.status.emit("SISTEMA DESLIGADO")


class CoreOrb(QWidget):

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




class MainWindow(QMainWindow):

    def __init__(self):

        super().__init__()

        self.setWindowTitle("J.A.R.V.I.S. | Personal AI")
        self.resize(1380, 850)
        self.setMinimumSize(1050, 700)

        self.setStyleSheet("""
            QMainWindow, QWidget {
                background-color: #080F1C;
                color: #E6F5FF;
                font-family: 'Segoe UI';
            }

            QLabel {
                background-color: transparent;
            }

            QFrame#Sidebar {
                background-color: #0B1525;
                border-right: 1px solid #172B40;
            }

            QFrame#Card {
                background-color: #0D1B2D;
                border: 1px solid #19334D;
                border-radius: 17px;
            }

            QLabel#Logo {
                color: #60D9FF;
                font-size: 24px;
                font-weight: bold;
                letter-spacing: 3px;
            }

            QLabel#Subtitle {
                color: #698AA8;
                font-size: 10px;
                letter-spacing: 2px;
            }

            QLabel#SectionTitle {
                color: #8AB7D8;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 2px;
            }

            QLabel#MainTitle {
                color: #EAF8FF;
                font-size: 23px;
                font-weight: bold;
            }

            QLabel#Status {
                color: #50D9FF;
                font-size: 12px;
                font-weight: bold;
                letter-spacing: 1px;
            }

            QLabel#Muted {
                color: #7892AA;
                font-size: 11px;
            }

            QLineEdit {
                background-color: #091421;
                color: #EAF8FF;
                border: 1px solid #254662;
                border-radius: 11px;
                padding: 14px;
                font-size: 13px;
            }

            QLineEdit:focus {
                border: 1px solid #35C9F5;
            }

            QPushButton {
                background-color: #102B42;
                color: #7FE5FF;
                border: 1px solid #24516D;
                border-radius: 10px;
                padding: 11px 16px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #174363;
                border: 1px solid #4BD5FF;
            }

            QPushButton#SendButton {
                background-color: #087EA8;
                color: white;
                border: none;
                min-width: 80px;
            }

            QPushButton#SendButton:hover {
                background-color: #0B9CCB;
            }

            QPushButton:checked {
                background-color: #153C37;
                color: #67E7B4;
                border: 1px solid #287B68;
            }

            QScrollArea {
                border: none;
                background: transparent;
            }

            QScrollBar:vertical {
                background: #0B1525;
                width: 7px;
                border-radius: 3px;
            }

            QScrollBar::handle:vertical {
                background: #27506D;
                border-radius: 3px;
            }
        """)

        self.worker = JarvisWorker()

        conversas = listar_conversas()
        if conversas:
            self.current_conversation_id = conversas[0][0]
        else:
            self.current_conversation_id = criar_conversa()

        self.worker.set_conversation(self.current_conversation_id)

        self.build_interface()
        self.connect_worker()
        self.refresh_conversation_list(self.current_conversation_id)
        self.load_conversation(self.current_conversation_id)

        self.worker.start()

    def build_interface(self):

        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # BARRA LATERAL
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)

        side = QVBoxLayout(sidebar)
        side.setContentsMargins(22, 28, 22, 22)
        side.setSpacing(12)

        logo = QLabel("J.A.R.V.I.S.")
        logo.setObjectName("Logo")

        subtitle = QLabel("SISTEMA DE INTELIGÊNCIA INTEGRADO")
        subtitle.setObjectName("Subtitle")

        side.addWidget(logo)
        side.addWidget(subtitle)
        side.addSpacing(35)

        nav_title = QLabel("CONVERSAS")
        nav_title.setObjectName("SectionTitle")
        side.addWidget(nav_title)

        self.new_chat_button = QPushButton("+  Nova conversa")
        self.new_chat_button.clicked.connect(self.new_conversation)
        side.addWidget(self.new_chat_button)

        self.conversation_list = QListWidget()
        self.conversation_list.setEnabled(True)
        self.conversation_list.setMinimumHeight(180)
        self.conversation_list.setSelectionMode(
            QListWidget.SelectionMode.SingleSelection
        )
        self.conversation_list.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )
        self.conversation_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.conversation_list.setStyleSheet("""
            QListWidget {
                background: #091421;
                color: #B9D8EA;
                border: 1px solid #19334D;
                border-radius: 10px;
                padding: 5px;
                outline: none;
                font-size: 11px;
            }
            QListWidget::item {
                padding: 12px 7px;
                border-radius: 7px;
            }
            QListWidget::item:selected {
                background: #123D59;
                color: #70E0FF;
                border-left: 3px solid #42CFFF;
            }
            QListWidget::item:hover {
                background: #102B42;
            }
        """)
        self.conversation_list.itemClicked.connect(self.open_conversation)
        side.addWidget(self.conversation_list, 1)

        conversation_actions = QHBoxLayout()

        self.rename_button = QPushButton("Renomear")
        self.rename_button.clicked.connect(
            self.rename_current_conversation
        )

        self.delete_button = QPushButton("Excluir")
        self.delete_button.clicked.connect(
            self.delete_current_conversation
        )

        conversation_actions.addWidget(self.rename_button)
        conversation_actions.addWidget(self.delete_button)
        side.addLayout(conversation_actions)

        side.addStretch()

        local_label = QLabel("JARVIS DESKTOP")
        local_label.setStyleSheet("color:#56D5FF; font-weight:bold;")

        version = QLabel("ASSISTENTE PESSOAL")
        version.setObjectName("Muted")

        side.addWidget(local_label)
        side.addWidget(version)

        root.addWidget(sidebar)

        # CONTEUDO PRINCIPAL
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 28, 24)
        content_layout.setSpacing(20)

        topbar = QHBoxLayout()

        title_box = QVBoxLayout()
        title = QLabel("Painel de controle")
        title.setObjectName("MainTitle")

        subtitle_top = QLabel(
            "CENTRAL DE INTELIGENCIA E COMUNICACAO"
        )
        subtitle_top.setObjectName("Subtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle_top)

        topbar.addLayout(title_box)
        topbar.addStretch()

        self.online_label = QLabel("● INICIALIZANDO")
        self.online_label.setObjectName("Status")
        topbar.addWidget(self.online_label)

        content_layout.addLayout(topbar)

        body = QHBoxLayout()
        body.setSpacing(18)

        # PAINEL DO NUCLEO
        core_card = QFrame()
        core_card.setObjectName("Card")
        core_card.setMinimumWidth(340)
        core_card.setMaximumWidth(390)

        core_layout = QVBoxLayout(core_card)
        core_layout.setContentsMargins(20, 20, 20, 20)
        core_layout.setSpacing(12)

        core_title = QLabel("NUCLEO CENTRAL")
        core_title.setObjectName("SectionTitle")
        core_layout.addWidget(core_title)

        self.orb = CoreOrb()
        core_layout.addWidget(self.orb, 1)

        self.core_state = QLabel("SISTEMA INICIALIZANDO")
        self.core_state.setObjectName("Status")
        self.core_state.setAlignment(Qt.AlignmentFlag.AlignCenter)
        core_layout.addWidget(self.core_state)

        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setStyleSheet("color:#1B344B;")
        core_layout.addWidget(divider)

        self.indicators = {}

        indicator_rows = [
            [
                ("INTELIGÊNCIA", "intelligence", "Online",
                 "Pronta para processar"),
                ("MEMÓRIA", "memory", "Disponível",
                 "Históricos preservados")
            ],
            [
                ("CAPTAÇÃO", "capture", "Ativa",
                 "Aguardando sua voz"),
                ("COMUNICAÇÃO", "communication", "Pronta",
                 "Resposta por voz")
            ]
        ]

        indicator_grid = QVBoxLayout()
        indicator_grid.setSpacing(9)

        for row_data in indicator_rows:
            indicator_row = QHBoxLayout()
            indicator_row.setSpacing(9)

            for heading, key, initial_state, description in row_data:
                card = QFrame()
                card.setObjectName("IndicatorCard")
                card.setMinimumHeight(86)

                card.setStyleSheet("""
                    QFrame#IndicatorCard {
                        background-color: #10243A;
                        border: 1px solid #1B3B55;
                        border-radius: 11px;
                    }
                    QFrame#IndicatorCard QLabel {
                        background: transparent;
                        border: none;
                    }
                """)

                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(10, 8, 10, 8)
                card_layout.setSpacing(3)

                heading_label = QLabel(heading)
                heading_label.setStyleSheet(
                    "color:#83AFCB; font-size:9px; "
                    "font-weight:bold; letter-spacing:1px;"
                )

                state_label = QLabel(initial_state)
                state_label.setStyleSheet(
                    "color:#53E6B5; font-size:13px; "
                    "font-weight:bold;"
                )

                description_label = QLabel(description)
                description_label.setWordWrap(True)
                description_label.setStyleSheet(
                    "color:#83A5BF; font-size:9px;"
                )

                card_layout.addWidget(heading_label)
                card_layout.addWidget(state_label)
                card_layout.addWidget(description_label)
                card_layout.addStretch()

                self.indicators[key] = (
                    state_label,
                    description_label
                )

                indicator_row.addWidget(card, 1)

            indicator_grid.addLayout(indicator_row)

        core_layout.addLayout(indicator_grid)

        body.addWidget(core_card)

        # PAINEL DE CONVERSA
        chat_card = QFrame()
        chat_card.setObjectName("Card")

        chat_layout = QVBoxLayout(chat_card)
        chat_layout.setContentsMargins(20, 20, 20, 18)
        chat_layout.setSpacing(12)

        chat_header = QHBoxLayout()

        chat_title_box = QVBoxLayout()

        chat_title = QLabel("Conversas")
        chat_title.setStyleSheet(
            "font-size:19px; font-weight:bold; color:#E9F7FF;"
        )

        chat_description = QLabel(
            "COMUNIQUE-SE COM SEU ASSISTENTE"
        )
        chat_description.setObjectName("Subtitle")

        chat_title_box.addWidget(chat_title)
        chat_title_box.addWidget(chat_description)

        chat_header.addLayout(chat_title_box)
        chat_header.addStretch()

        self.mic_button = QPushButton("MICROFONE ATIVO")
        self.mic_button.setCheckable(True)
        self.mic_button.setChecked(True)
        self.mic_button.clicked.connect(self.toggle_microphone)

        chat_header.addWidget(self.mic_button)
        chat_layout.addLayout(chat_header)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.chat_container = QWidget()
        self.message_layout = QVBoxLayout(self.chat_container)
        self.message_layout.setContentsMargins(5, 8, 5, 8)
        self.message_layout.setSpacing(15)
        self.message_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll.setWidget(self.chat_container)
        chat_layout.addWidget(self.scroll, 1)

        self.metrics_label = QLabel(
            "JARVIS | PRONTO PARA AJUDAR"
        )
        self.metrics_label.setObjectName("Muted")

        chat_layout.addWidget(self.metrics_label)

        composer = QHBoxLayout()
        composer.setSpacing(10)

        self.input = QLineEdit()
        self.input.setPlaceholderText(
            "Digite uma mensagem ou fale com o JARVIS..."
        )
        self.input.returnPressed.connect(self.send_message)

        send_button = QPushButton("ENVIAR")
        send_button.setObjectName("SendButton")
        send_button.clicked.connect(self.send_message)

        composer.addWidget(self.input, 1)
        composer.addWidget(send_button)

        chat_layout.addLayout(composer)

        body.addWidget(chat_card, 1)

        content_layout.addLayout(body, 1)

        self.footer_status = QLabel(
            "J.A.R.V.I.S.  •  STATUS: INICIALIZANDO"
        )
        self.footer_status.setObjectName("Subtitle")
        content_layout.addWidget(self.footer_status)

        root.addWidget(content, 1)

    def connect_worker(self):

        self.worker.status.connect(self.update_status)
        self.worker.audio_level.connect(self.orb.set_audio_level)
        self.worker.transcription.connect(
            lambda text: self.add_message("VOCE", text)
        )
        self.worker.response.connect(
            lambda text: self.add_message("JARVIS", text)
        )
        self.worker.metrics.connect(lambda _text: self.metrics_label.setText("JARVIS | PRONTO PARA AJUDAR"))
        self.worker.error.connect(self.show_error)
        self.worker.conversation_changed.connect(
            self.refresh_after_message
        )

    def add_message(self, sender, text, scroll=True):

        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        bubble_layout = QVBoxLayout()

        sender_label = QLabel(sender)
        sender_label.setStyleSheet(
            "color:#51D5FA; font-size:10px; font-weight:bold;"
        )

        message = QLabel(text)
        message.setWordWrap(True)
        message.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        message.setMaximumWidth(650)

        message.setStyleSheet("""
            background-color: #132940;
            color: #E7F6FF;
            border: 1px solid #234661;
            border-radius: 12px;
            padding: 12px;
            font-size: 13px;
        """)

        if sender == "VOCE":
            message.setStyleSheet("""
                background-color: #103343;
                color: #E7F9FF;
                border: 1px solid #17617D;
                border-radius: 12px;
                padding: 12px;
                font-size: 13px;
            """)

        bubble_layout.addWidget(sender_label)
        bubble_layout.addWidget(message)

        layout.addLayout(bubble_layout)

        if sender == "VOCE":
            layout.insertStretch(0, 1)
        else:
            layout.addStretch()

        self.message_layout.addWidget(row)

        if scroll:
            QTimer.singleShot(0, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def set_indicator(self, key, state, description, color="#53E6B5"):
        if key not in self.indicators:
            return

        state_label, description_label = self.indicators[key]

        state_label.setText(state)
        description_label.setText(description)

        state_label.setStyleSheet(
            f"color:{color}; font-size:13px; font-weight:bold;"
        )

    def update_indicators(self, text):

        if text == "CARREGANDO WHISPER":
            self.set_indicator(
                "intelligence", "Iniciando",
                "Preparando assistente", "#55D9FF"
            )
            self.set_indicator(
                "capture", "Iniciando",
                "Preparando microfone", "#55D9FF"
            )
            self.set_indicator(
                "communication", "Iniciando",
                "Preparando resposta por voz", "#55D9FF"
            )

        elif text in ("SISTEMA ONLINE", "MICROFONE ATIVO"):
            self.set_indicator(
                "intelligence", "Online",
                "Pronta para processar"
            )
            self.set_indicator(
                "communication", "Pronta",
                "Resposta por voz"
            )

            mic_ativo = self.worker.mic_enabled.is_set()

            self.set_indicator(
                "capture",
                "Ativa" if mic_ativo else "Pausada",
                "Aguardando sua voz" if mic_ativo
                else "Microfone desativado",
                "#53E6B5" if mic_ativo else "#E7BC70"
            )

        elif text == "AGUARDANDO SUA VOZ":
            self.set_indicator(
                "intelligence", "Online",
                "Pronta para processar"
            )
            self.set_indicator(
                "capture", "Ativa",
                "Aguardando sua voz"
            )
            self.set_indicator(
                "communication", "Pronta",
                "Resposta por voz"
            )

        elif text == "OUVINDO VOCE":
            self.set_indicator(
                "capture", "Ativa",
                "Ouvindo sua voz"
            )

        elif text == "PROCESSANDO AUDIO":
            self.set_indicator(
                "capture", "Processando",
                "Analisando áudio recebido", "#55D9FF"
            )

        elif text == "RECONHECENDO VOZ":
            self.set_indicator(
                "capture", "Processando",
                "Interpretando sua fala", "#55D9FF"
            )

        elif text == "PENSANDO...":
            self.set_indicator(
                "intelligence", "Pensando...",
                "Analisando sua solicitação", "#55D9FF"
            )
            self.set_indicator(
                "capture", "Em espera",
                "Aguardando resposta", "#55D9FF"
            )
            self.set_indicator(
                "communication", "Preparando",
                "Preparando resposta por voz", "#55D9FF"
            )

        elif text == "FALANDO":
            self.set_indicator(
                "intelligence", "Online",
                "Processamento concluído"
            )
            self.set_indicator(
                "capture", "Em espera",
                "Aguardando a resposta", "#55D9FF"
            )
            self.set_indicator(
                "communication", "Falando",
                "Resposta por voz", "#55D9FF"
            )

        elif text == "MICROFONE PAUSADO":
            self.set_indicator(
                "capture", "Pausada",
                "Microfone desativado", "#E7BC70"
            )
            self.set_indicator(
                "communication", "Pronta",
                "Resposta por voz"
            )

        elif text == "ERRO NO SISTEMA":
            self.set_indicator(
                "intelligence", "Indisponível",
                "Verifique o sistema", "#FF7373"
            )
            self.set_indicator(
                "communication", "Indisponível",
                "Verifique o sistema", "#FF7373"
            )

        elif text in ("ENCERRANDO", "SISTEMA DESLIGADO"):
            self.set_indicator(
                "intelligence", "Offline",
                "Sistema encerrado", "#E7BC70"
            )
            self.set_indicator(
                "capture", "Inativa",
                "Captação encerrada", "#E7BC70"
            )
            self.set_indicator(
                "communication", "Inativa",
                "Comunicação encerrada", "#E7BC70"
            )

    def update_status(self, text):

        nomes_status = {
            "CARREGANDO WHISPER": "INICIALIZANDO",
            "SISTEMA ONLINE": "ONLINE",
            "AGUARDANDO SUA VOZ": "AGUARDANDO COMANDO",
            "OUVINDO VOCE": "OUVINDO SUA VOZ",
            "PROCESSANDO AUDIO": "ANALISANDO AUDIO",
            "RECONHECENDO VOZ": "INTERPRETANDO VOZ",
            "PENSANDO...": "PENSANDO...",
            "FALANDO": "FALANDO",
            "MICROFONE ATIVO": "MICROFONE ATIVO",
            "MICROFONE PAUSADO": "MICROFONE PAUSADO",
            "ERRO NO SISTEMA": "ATENCAO: ERRO",
            "ENCERRANDO": "ENCERRANDO",
            "SISTEMA DESLIGADO": "OFFLINE"
        }

        status_exibido = nomes_status.get(text, text)

        self.online_label.setText("● " + status_exibido)
        self.core_state.setText(status_exibido)
        self.footer_status.setText(
            "J.A.R.V.I.S.  •  STATUS: " + status_exibido
        )

        if text in ("SISTEMA ONLINE", "MICROFONE ATIVO"):
            self.online_label.setStyleSheet(
                "color:#53E6B5; font-weight:bold;"
            )
        elif text == "ERRO NO SISTEMA":
            self.online_label.setStyleSheet(
                "color:#FF7373; font-weight:bold;"
            )
        else:
            self.online_label.setStyleSheet(
                "color:#55D9FF; font-weight:bold;"
            )

        self.orb.set_state(text)
        self.update_indicators(text)

    def toggle_microphone(self, checked):

        self.worker.set_microphone(checked)

        if checked:
            self.mic_button.setText("MICROFONE ATIVO")
        else:
            self.mic_button.setText("MICROFONE PAUSADO")

    def send_message(self):

        text = self.input.text().strip()

        if not text:
            return

        self.input.clear()
        self.worker.submit_text(text)

    def refresh_after_message(self):
        self.refresh_conversation_list(self.current_conversation_id)

    def refresh_conversation_list(self, selected_id=None):
        self.conversation_list.blockSignals(True)
        self.conversation_list.clear()

        selected_item = None

        for conversation_id, title, updated_at in listar_conversas():
            item = QListWidgetItem(title)
            item.setData(Qt.ItemDataRole.UserRole, conversation_id)
            self.conversation_list.addItem(item)

            if conversation_id == selected_id:
                selected_item = item

        if selected_item:
            self.conversation_list.setCurrentItem(selected_item)

        self.conversation_list.blockSignals(False)

    def clear_messages(self):
        while self.message_layout.count():
            item = self.message_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def load_conversation(self, conversation_id):
        self.chat_container.setUpdatesEnabled(False)

        try:
            self.clear_messages()
            mensagens = obter_mensagens_conversa(conversation_id)

            if not mensagens:
                self.add_message(
                    "JARVIS",
                    "Nova conversa iniciada. Como posso ajudar?",
                    scroll=False
                )
            else:
                for _, role, content, created_at in mensagens:
                    sender = "VOCE" if role == "user" else "JARVIS"
                    self.add_message(sender, content, scroll=False)

        finally:
            self.chat_container.setUpdatesEnabled(True)

        QTimer.singleShot(0, self.scroll_to_bottom)

    def open_conversation(self, item):
        conversation_id = item.data(Qt.ItemDataRole.UserRole)

        if conversation_id is None:
            return

        self.current_conversation_id = conversation_id
        self.worker.set_conversation(conversation_id)
        self.load_conversation(conversation_id)

    def new_conversation(self):
        conversation_id = criar_conversa()
        self.current_conversation_id = conversation_id
        self.worker.set_conversation(conversation_id)
        self.refresh_conversation_list(conversation_id)
        self.load_conversation(conversation_id)

    def rename_current_conversation(self):
        conversas = listar_conversas()
        atual = next(
            (c for c in conversas if c[0] == self.current_conversation_id),
            None
        )

        if not atual:
            return

        novo_nome, confirmado = QInputDialog.getText(
            self,
            "Renomear conversa",
            "Digite o novo nome:",
            text=atual[1]
        )

        if confirmado and novo_nome.strip():
            renomear_conversa(self.current_conversation_id, novo_nome)
            self.refresh_conversation_list(self.current_conversation_id)

    def delete_current_conversation(self):
        resposta = QMessageBox.question(
            self,
            "Excluir conversa",
            "Deseja excluir esta conversa e todas as suas mensagens?",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if resposta != QMessageBox.StandardButton.Yes:
            return

        excluir_conversa(self.current_conversation_id)
        conversas = listar_conversas()

        if conversas:
            self.current_conversation_id = conversas[0][0]
        else:
            self.current_conversation_id = criar_conversa()

        self.worker.set_conversation(self.current_conversation_id)
        self.refresh_conversation_list(self.current_conversation_id)
        self.load_conversation(self.current_conversation_id)

    def show_error(self, message):

        self.add_message(
            "SISTEMA",
            "Ocorreu um erro: " + message
        )

    def closeEvent(self, event):

        if self.worker.isRunning():
            self.worker.stop()
            self.setWindowTitle(
                "J.A.R.V.I.S. | Encerrando sistemas..."
            )
            event.ignore()
            self.worker.finished.connect(self.close)
        else:
            event.accept()


def main():

    app = QApplication(sys.argv)
    app.setApplicationName("JARVIS")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
