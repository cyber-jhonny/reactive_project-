from pathlib import Path

p = Path("interface.py")
s = p.read_text(encoding="utf-8-sig")

# Substituir os quatro indicadores antigos por cards
inicio = s.index("        for heading, value in (", s.index("class MainWindow"))
fim = s.index("        body.addWidget(core_card)", inicio)

novo_painel = '''        self.indicators = {}

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

'''

s = s[:inicio] + novo_painel + s[fim:]

# Adicionar atualizacao dinamica dos indicadores
marcador = "    def update_status(self, text):"

metodo = '''    def set_indicator(self, key, state, description, color="#53E6B5"):
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

'''

if s.count(marcador) != 1:
    raise SystemExit("Funcao update_status nao encontrada.")

s = s.replace(marcador, metodo + marcador, 1)

# Atualizar os indicadores em cada mudanca de estado
marcador_orb = "        self.orb.set_state(text)"

if s.count(marcador_orb) != 1:
    raise SystemExit("Atualizacao do nucleo nao encontrada.")

s = s.replace(
    marcador_orb,
    marcador_orb + "\n        self.update_indicators(text)",
    1
)

p.write_text(s, encoding="utf-8")

print("PAINEL ATUALIZADO COM SUCESSO!")
print("INTELIGENCIA, MEMORIA, CAPTACAO E COMUNICACAO.")
