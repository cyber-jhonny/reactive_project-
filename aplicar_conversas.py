from pathlib import Path

p = Path("interface.py")
s = p.read_text(encoding="utf-8-sig")

def replace_once(old, new, label):
    global s
    count = s.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: esperava 1 trecho, encontrei {count}")
    s = s.replace(old, new, 1)

# Importar os componentes e funcoes do historico
replace_once(
    "    QScrollArea, QSizePolicy\n)",
    "    QScrollArea, QSizePolicy, QListWidget, QListWidgetItem,\n"
    "    QInputDialog, QMessageBox\n)",
    "Imports da interface"
)

replace_once(
    "from modulos.inteligencia import conversar\nfrom voz.falar import falar",
    "from modulos.inteligencia import conversar\n"
    "from modulos.memoria import (\n"
    "    criar_conversa, listar_conversas, obter_mensagens_conversa,\n"
    "    renomear_conversa, excluir_conversa\n"
    ")\n"
    "from voz.falar import falar",
    "Import da memoria"
)

# Adicionar identificador de conversa ao trabalhador
replace_once(
    "    error = Signal(str)\n",
    "    error = Signal(str)\n    conversation_changed = Signal()\n",
    "Sinal de conversa"
)

replace_once(
    "        self.text_queue = queue.Queue()\n        self.modelo = None",
    "        self.text_queue = queue.Queue()\n"
    "        self.modelo = None\n"
    "        self.conversation_id = None\n"
    "        self.conversation_lock = threading.Lock()",
    "Estado da conversa"
)

replace_once(
    "    def set_microphone(self, enabled):",
    "    def set_conversation(self, conversation_id):\n"
    "        with self.conversation_lock:\n"
    "            self.conversation_id = conversation_id\n\n"
    "    def get_conversation(self):\n"
    "        with self.conversation_lock:\n"
    "            return self.conversation_id\n\n"
    "    def set_microphone(self, enabled):",
    "Metodos do trabalhador"
)

replace_once(
    "        answer = conversar(text)\n"
    "        gemini_time = time.perf_counter() - start_gemini",
    "        conversation_id = self.get_conversation()\n"
    "        answer = conversar(text, conversation_id)\n"
    "        self.conversation_changed.emit()\n"
    "        gemini_time = time.perf_counter() - start_gemini",
    "Conexao com a inteligencia"
)

# Inicializar a conversa selecionada antes de construir a janela
old_init = '''        self.worker = JarvisWorker()

        self.build_interface()
        self.connect_worker()

        self.add_message(
            "JARVIS",
            "Olá! Minha interface está pronta. Estou inicializando meus sistemas."
        )

        self.worker.start()'''

new_init = '''        self.worker = JarvisWorker()

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

        self.worker.start()'''

replace_once(old_init, new_init, "Inicializacao da janela")

# Substituir os textos estaticos por uma lista clicavel
start = s.index('        nav_title = QLabel("NAVEGACAO")')
end = s.index('        local_label = QLabel("JARVIS DESKTOP")', start)

menu = '''        nav_title = QLabel("CONVERSAS")
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

'''

s = s[:start] + menu + s[end:]

# Atualizar a lista depois de cada mensagem respondida
replace_once(
    "        self.worker.error.connect(self.show_error)",
    "        self.worker.error.connect(self.show_error)\n"
    "        self.worker.conversation_changed.connect(\n"
    "            self.refresh_after_message\n"
    "        )",
    "Conexao dos sinais"
)

# Funcoes da lista de conversas
marker = "    def show_error(self, message):"

methods = '''    def refresh_after_message(self):
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
        self.clear_messages()
        mensagens = obter_mensagens_conversa(conversation_id)

        if not mensagens:
            self.add_message(
                "JARVIS",
                "Nova conversa iniciada. Como posso ajudar?"
            )
            return

        for _, role, content, created_at in mensagens:
            sender = "VOCE" if role == "user" else "JARVIS"
            self.add_message(sender, content)

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

'''

replace_once(marker, methods + marker, "Funcoes de gerenciamento")

p.write_text(s, encoding="utf-8")
print("SUCESSO: lista de conversas instalada.")
print("SUCESSO: abrir, criar, renomear e excluir adicionados.")
