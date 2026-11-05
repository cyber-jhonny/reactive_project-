from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys

path = Path("interface.py")
source = path.read_text(encoding="utf-8")

# Evita aplicar a mesma alteração duas vezes.
if "# JARVIS_MONITORING_NAV" in source:
    print("A navegação do monitoramento já foi instalada. Nenhuma alteração feita.")
    sys.exit(0)

# Confere todos os pontos de inserção antes de modificar o arquivo.
checks = {
    "import": "    QInputDialog, QMessageBox\n",
    "menu": "        side.addSpacing(35)\n",
    "conteudo": "        root.addWidget(content, 1)\n",
    "fim": "\ndef main():\n",
}

for name, anchor in checks.items():
    if source.count(anchor) != 1:
        print(f"ERRO: ponto de inserção '{name}' não encontrado de forma única.")
        print("Nenhuma alteração foi feita.")
        sys.exit(1)

backup = Path(
    f"interface.backup_monitoramento_{datetime.now():%Y%m%d_%H%M%S}.py"
)
shutil.copy2(path, backup)

try:
    # 1. Importa o componente de páginas.
    source = source.replace(
        checks["import"],
        "    QInputDialog, QMessageBox, QStackedWidget\n",
        1
    )

    # 2. Adiciona a navegação ao menu lateral.
    nav_code = '''        # JARVIS_MONITORING_NAV
        self.dashboard_button = QPushButton("⌂  PAINEL PRINCIPAL")
        self.dashboard_button.setCheckable(True)
        self.dashboard_button.clicked.connect(
            lambda: self.show_page(0)
        )
        side.addWidget(self.dashboard_button)

        self.monitor_button = QPushButton("▦  MONITORAMENTO")
        self.monitor_button.setCheckable(True)
        self.monitor_button.clicked.connect(
            lambda: self.show_page(1)
        )
        side.addWidget(self.monitor_button)

        self.dashboard_button.setChecked(True)

'''
    source = source.replace(
        checks["menu"],
        checks["menu"] + "\n" + nav_code,
        1
    )

    # 3. Coloca o painel atual e o monitoramento em páginas separadas.
    stack_code = '''        self.pages = QStackedWidget()
        self.pages.addWidget(content)

        self.monitoring_page = self.build_monitoring_page()
        self.pages.addWidget(self.monitoring_page)

        root.addWidget(self.pages, 1)
'''
    source = source.replace(
        checks["conteudo"],
        stack_code,
        1
    )

    # 4. Cria os métodos da nova página.
    methods = '''
    def show_page(self, index):
        self.pages.setCurrentIndex(index)
        self.dashboard_button.setChecked(index == 0)
        self.monitor_button.setChecked(index == 1)

    def build_monitoring_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(20)

        header = QHBoxLayout()
        title_box = QVBoxLayout()

        title = QLabel("Central de Monitoramento")
        title.setObjectName("MainTitle")

        subtitle = QLabel(
            "DIAGNOSTICO, BENCHMARK E DESEMPENHO DO COMPUTADOR"
        )
        subtitle.setObjectName("Subtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        status = QLabel("SENSORES AINDA NÃO CONECTADOS")
        status.setObjectName("Status")
        header.addWidget(status)
        layout.addLayout(header)

        description = QLabel(
            "Visão geral do hardware — os dados serão exibidos "
            "após a integração dos sensores reais."
        )
        description.setObjectName("Muted")
        description.setWordWrap(True)
        layout.addWidget(description)

        rows = [
            [
                ("PROCESSADOR", "CPU", "Ryzen 5 5600"),
                ("PLACA DE VÍDEO", "GPU", "Radeon RX 7600"),
                ("MEMÓRIA RAM", "RAM", "16 GB")
            ],
            [
                ("ARMAZENAMENTO", "SSD", "Aguardando identificação"),
                ("REDE", "REDE", "Aguardando identificação"),
                ("DESEMPENHO", "BENCHMARK", "Nenhum teste executado")
            ]
        ]

        for row_data in rows:
            row = QHBoxLayout()
            row.setSpacing(14)

            for heading, key, detail in row_data:
                card = QFrame()
                card.setObjectName("Card")
                card.setMinimumHeight(145)

                card_layout = QVBoxLayout(card)
                card_layout.setContentsMargins(17, 16, 17, 16)
                card_layout.setSpacing(9)

                heading_label = QLabel(heading)
                heading_label.setObjectName("SectionTitle")

                value_label = QLabel("--")
                value_label.setStyleSheet(
                    "color:#60D9FF; font-size:27px; "
                    "font-weight:bold;"
                )

                detail_label = QLabel(detail)
                detail_label.setObjectName("Muted")
                detail_label.setWordWrap(True)

                sensor_label = QLabel("AGUARDANDO INTEGRAÇÃO")
                sensor_label.setStyleSheet(
                    "color:#D5A84B; font-size:9px; "
                    "font-weight:bold; letter-spacing:1px;"
                )

                card_layout.addWidget(heading_label)
                card_layout.addWidget(value_label)
                card_layout.addWidget(detail_label)
                card_layout.addStretch()
                card_layout.addWidget(sensor_label)

                row.addWidget(card, 1)

            layout.addLayout(row)

        layout.addStretch()

        note = QLabel(
            "JARVIS DIAGNOSTICS | Benchmarks reais e sensores "
            "serão integrados nas próximas etapas."
        )
        note.setObjectName("Subtitle")
        layout.addWidget(note)

        return page

'''
    source = source.replace(
        checks["fim"],
        "\n" + methods + checks["fim"],
        1
    )

    # Grava somente depois de todas as verificações.
    path.write_text(source, encoding="utf-8")

    # Valida a sintaxe sem executar o JARVIS.
    py_compile.compile(str(path), doraise=True)

    print("SUCESSO: página de monitoramento instalada.")
    print(f"Backup criado: {backup}")
    print("Sintaxe Python validada com sucesso.")

except Exception as exc:
    shutil.copy2(backup, path)
    print(f"ERRO: {exc}")
    print("Arquivo original restaurado pelo backup.")
    sys.exit(1)
