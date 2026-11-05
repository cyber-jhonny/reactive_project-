from pathlib import Path
from datetime import datetime
import shutil
import py_compile

arquivo = Path("interface.py")
codigo = arquivo.read_text(encoding="utf-8-sig")

backup = Path(
    "interface.py.backup_scroll_" +
    datetime.now().strftime("%Y%m%d_%H%M%S")
)
shutil.copy2(arquivo, backup)

metodo_antigo = '''    def scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
'''

metodo_novo = '''    def scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()

        def ir_para_baixo():
            bar.setValue(bar.maximum())

        self.chat_container.adjustSize()
        self.chat_container.updateGeometry()

        ir_para_baixo()
        QTimer.singleShot(50, ir_para_baixo)
        QTimer.singleShot(150, ir_para_baixo)
'''

if metodo_antigo in codigo:
    codigo = codigo.replace(metodo_antigo, metodo_novo, 1)
elif metodo_novo not in codigo:
    raise SystemExit("ERRO: nao encontrei scroll_to_bottom.")

# Acompanhar alteracoes na altura da conversa.
conexao = '''        self.scroll.verticalScrollBar().rangeChanged.connect(
            lambda _minimum, _maximum: QTimer.singleShot(
                0, self.scroll_to_bottom
            )
        )
'''

marcador = "        self.scroll.setWidget(self.chat_container)"

if conexao.strip() not in codigo:
    if marcador not in codigo:
        raise SystemExit("ERRO: nao encontrei a criacao da area de conversa.")

    codigo = codigo.replace(
        marcador,
        marcador + "\n" + conexao.rstrip(),
        1
    )

# Salvar e validar.
arquivo.write_text(codigo, encoding="utf-8")
py_compile.compile(str(arquivo), doraise=True)

print("CORRECAO CONCLUIDA!")
print("Rolagem automatica: OK")
print("Ajuste de layout: OK")
print("Backup:", backup)
print("Compilacao: OK")
