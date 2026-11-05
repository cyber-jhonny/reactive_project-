from pathlib import Path

p = Path("interface.py")
s = p.read_text(encoding="utf-8-sig")

def replace_once(old, new, name):
    global s
    if s.count(old) != 1:
        raise RuntimeError(f"Trecho não localizado corretamente: {name}")
    s = s.replace(old, new, 1)

# Permitir criar mensagens sem atualizar a rolagem individualmente
replace_once(
    "    def add_message(self, sender, text):",
    "    def add_message(self, sender, text, scroll=True):",
    "assinatura de add_message"
)

bloco_antigo = '''        QTimer.singleShot(
            50,
            lambda: self.scroll.verticalScrollBar().setValue(
                self.scroll.verticalScrollBar().maximum()
            )
        )'''

bloco_novo = '''        if scroll:
            QTimer.singleShot(0, self.scroll_to_bottom)'''

replace_once(bloco_antigo, bloco_novo, "rolagem das mensagens")

# Substituir carregamento individual por carregamento em lote
inicio = s.index("    def load_conversation(self, conversation_id):")
fim = s.index("    def open_conversation(", inicio)

novo_carregamento = '''    def load_conversation(self, conversation_id):
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

'''

s = s[:inicio] + novo_carregamento + s[fim:]

# Método único para rolar até o final
replace_once(
    "    def update_status(self, text):",
    "    def scroll_to_bottom(self):\n"
    "        bar = self.scroll.verticalScrollBar()\n"
    "        bar.setValue(bar.maximum())\n\n"
    "    def update_status(self, text):",
    "metodo de rolagem"
)

p.write_text(s, encoding="utf-8")
print("OTIMIZACAO APLICADA COM SUCESSO!")
print("Mensagens agora sao carregadas em lote.")
print("Rolagem atualizada apenas uma vez por conversa.")
