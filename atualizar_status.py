from pathlib import Path

p = Path("interface.py")
s = p.read_text(encoding="utf-8-sig")

antigo_footer = '''        footer = QLabel(
            "J.A.R.V.I.S.  •  SISTEMA PESSOAL  •  CONEXAO LOCAL"
        )
        footer.setObjectName("Subtitle")
        content_layout.addWidget(footer)'''

novo_footer = '''        self.footer_status = QLabel(
            "J.A.R.V.I.S.  •  STATUS: INICIALIZANDO"
        )
        self.footer_status.setObjectName("Subtitle")
        content_layout.addWidget(self.footer_status)'''

if s.count(antigo_footer) != 1:
    raise SystemExit("Barra inferior não encontrada. Arquivo não alterado.")

s = s.replace(antigo_footer, novo_footer, 1)

antigo_status = '''        self.online_label.setText("● " + text)
        self.core_state.setText(text)'''

novo_status = '''        nomes_status = {
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
        )'''

if s.count(antigo_status) != 1:
    raise SystemExit("Função de status não encontrada. Arquivo não alterado.")

s = s.replace(antigo_status, novo_status, 1)

p.write_text(s, encoding="utf-8")
print("Barra de status do JARVIS atualizada!")
