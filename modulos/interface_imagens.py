from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QPlainTextEdit, QComboBox,
    QMessageBox
)

from modulos.geracao_imagens import gerar_imagem


class ImageGenerationWorker(QThread):

    image_ready = Signal(str)
    generation_error = Signal(str)

    def __init__(self, prompt, aspect_ratio, image_size):
        super().__init__()

        self.prompt = prompt
        self.aspect_ratio = aspect_ratio
        self.image_size = image_size

    def run(self):
        try:
            caminho = gerar_imagem(
                self.prompt,
                aspect_ratio=self.aspect_ratio,
                image_size=self.image_size
            )

            self.image_ready.emit(str(caminho))

        except Exception as erro:
            self.generation_error.emit(str(erro))


class ImageGeneratorDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.worker = None
        self.image_path = None

        self.setWindowTitle("J.A.R.V.I.S. | GERACAO DE IMAGENS")
        self.resize(850, 720)
        self.setMinimumSize(650, 600)

        self.setStyleSheet("""
            QDialog {
                background-color: #071321;
                color: #E9F7FF;
            }

            QLabel {
                color: #D9ECFA;
            }

            QPlainTextEdit, QComboBox {
                background-color: #10243A;
                color: #E9F7FF;
                border: 1px solid #1B4968;
                border-radius: 8px;
                padding: 9px;
                font-size: 12px;
            }

            QPushButton {
                background-color: #087CC1;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 11px 18px;
                font-weight: bold;
            }

            QPushButton:hover {
                background-color: #1099E8;
            }

            QPushButton:disabled {
                background-color: #26394A;
                color: #8297A8;
            }
        """)

        self.build_interface()

    def build_interface(self):

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(13)

        title = QLabel("GERACAO DE IMAGENS")
        title.setStyleSheet(
            "font-size:21px; font-weight:bold; color:#65C7FF;"
        )

        subtitle = QLabel(
            "Descreva sua imagem e deixe o JARVIS criá-la."
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)

        prompt_label = QLabel("DESCRICAO DA IMAGEM")

        self.prompt_input = QPlainTextEdit()
        self.prompt_input.setPlaceholderText(
            "Ex.: Um cenário futurista cinematográfico, "
            "com iluminação azul, detalhes holográficos..."
        )
        self.prompt_input.setMinimumHeight(105)

        layout.addWidget(prompt_label)
        layout.addWidget(self.prompt_input)

        options = QHBoxLayout()

        ratio_box = QVBoxLayout()
        ratio_box.addWidget(QLabel("PROPORCAO"))

        self.ratio_combo = QComboBox()
        self.ratio_combo.addItems([
            "16:9",
            "1:1",
            "9:16",
            "4:3",
            "3:2"
        ])

        ratio_box.addWidget(self.ratio_combo)

        quality_box = QVBoxLayout()
        quality_box.addWidget(QLabel("RESOLUCAO"))

        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1K", "2K"])
        self.quality_combo.setCurrentText("2K")

        quality_box.addWidget(self.quality_combo)

        options.addLayout(ratio_box)
        options.addLayout(quality_box)

        layout.addLayout(options)

        self.generate_button = QPushButton("GERAR IMAGEM")
        self.generate_button.clicked.connect(
            self.start_generation
        )

        layout.addWidget(self.generate_button)

        self.status_label = QLabel(
            "SISTEMA PRONTO PARA GERAR"
        )
        self.status_label.setStyleSheet(
            "color:#65C7FF; font-weight:bold;"
        )

        layout.addWidget(self.status_label)

        self.preview = QLabel("A imagem gerada aparecerá aqui")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(300)
        self.preview.setStyleSheet("""
            QLabel {
                background-color: #0B1C2C;
                border: 1px solid #1B4968;
                border-radius: 10px;
                color: #7895AA;
                padding: 10px;
            }
        """)

        layout.addWidget(self.preview, 1)

        self.path_label = QLabel("")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet(
            "color:#83AFCB; font-size:10px;"
        )

        layout.addWidget(self.path_label)

    def start_generation(self):

        prompt = self.prompt_input.toPlainText().strip()

        if not prompt:
            QMessageBox.warning(
                self,
                "Descricao necessaria",
                "Digite uma descricao para gerar a imagem."
            )
            return

        if self.worker is not None:
            return

        self.generate_button.setEnabled(False)
        self.status_label.setText(
            "GERANDO IMAGEM... AGUARDE"
        )

        self.preview.setText(
            "O JARVIS esta processando sua solicitacao..."
        )
        self.preview.setPixmap(QPixmap())

        self.worker = ImageGenerationWorker(
            prompt,
            self.ratio_combo.currentText(),
            self.quality_combo.currentText()
        )

        self.worker.image_ready.connect(self.show_image)
        self.worker.generation_error.connect(self.show_generation_error)
        self.worker.finished.connect(self.worker_finished)
        self.worker.start()

    def show_image(self, caminho):

        self.image_path = caminho

        pixmap = QPixmap(caminho)

        if pixmap.isNull():
            self.preview.setText(
                "Imagem salva, mas nao foi possivel exibir a previa."
            )
        else:
            self.preview.setPixmap(
                pixmap.scaled(
                    self.preview.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            )

        self.path_label.setText(
            f"ARQUIVO SALVO: {caminho}"
        )

        self.status_label.setText(
            "IMAGEM GERADA COM SUCESSO"
        )

    def show_generation_error(self, erro):

        self.status_label.setText(
            "FALHA NA GERACAO DA IMAGEM"
        )

        self.preview.setText(
            "Nao foi possivel gerar a imagem."
        )

        QMessageBox.critical(
            self,
            "Erro na geracao",
            erro
        )

    def worker_finished(self):

        self.generate_button.setEnabled(True)

        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

    def resizeEvent(self, event):

        super().resizeEvent(event)

        if self.image_path and Path(self.image_path).exists():
            pixmap = QPixmap(self.image_path)

            if not pixmap.isNull():
                self.preview.setPixmap(
                    pixmap.scaled(
                        self.preview.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                )

    def closeEvent(self, event):

        if self.worker is not None and self.worker.isRunning():
            self.status_label.setText(
                "AGUARDE A CONCLUSAO DA GERACAO..."
            )
            event.ignore()
            return

        event.accept()
