from pathlib import Path
from datetime import datetime
import shutil
import py_compile

arquivo = Path("interface.py")
codigo = arquivo.read_text(encoding="utf-8-sig")

backup = Path(
    "interface.py.backup_scroll_final_"
    + datetime.now().strftime("%Y%m%d_%H%M%S")
)
shutil.copy2(arquivo, backup)

# 1. Remover o evento que pode criar o ciclo infinito.
conexao = '''        self.scroll.verticalScrollBar().rangeChanged.connect(
            lambda _minimum, _maximum: QTimer.singleShot(
                0, self.scroll_to_bottom
            )
        )
'''

codigo = codigo.replace(conexao, "")

# 2. Simplificar a funcao de rolagem.
inicio = codigo.find("    def scroll_to_bottom(self):")

if inicio < 0:
    raise SystemExit("ERRO: funcao scroll_to_bottom nao encontrada.")

fim = codigo.find("\n    def ", inicio + 10)

if fim < 0:
    raise SystemExit("ERRO: limite da funcao nao encontrado.")

nova_funcao = '''    def scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())
'''

codigo = codigo[:inicio] + nova_funcao + codigo[fim:]

# 3. Detectar se o usuario ja estava no final antes de inserir mensagem.
inicio = codigo.find("    def add_message(self, sender, text, scroll=True):")
fim = codigo.find("\n    def ", inicio + 10)

if inicio < 0 or fim < 0:
    raise SystemExit("ERRO: funcao add_message nao encontrada.")

trecho = codigo[inicio:fim]

marcador = "        row = QWidget()"

if "manter_no_final" not in trecho:
    if marcador not in trecho:
        raise SystemExit("ERRO: nao encontrei a criacao da mensagem.")

    captura = '''        barra = self.scroll.verticalScrollBar()
        manter_no_final = (
            barra.value() >= barra.maximum() - 40
        )

'''
    trecho = trecho.replace(marcador, captura + marcador, 1)

trecho = trecho.replace(
    '''        if scroll:
            QTimer.singleShot(0, self.scroll_to_bottom)
''',
    '''        if scroll and manter_no_final:
            QTimer.singleShot(60, self.scroll_to_bottom)
'''
)

codigo = codigo[:inicio] + trecho + codigo[fim:]

# 4. Carregar conversas antigas com uma unica rolagem ao final.
codigo = codigo.replace(
    "        QTimer.singleShot(0, self.scroll_to_bottom)",
    "        QTimer.singleShot(80, self.scroll_to_bottom)"
)

# 5. Garantir que nenhum evento rangeChanged continue conectado.
if "verticalScrollBar().rangeChanged.connect" in codigo:
    raise SystemExit(
        "ERRO: ainda existe uma conexao rangeChanged. "
        "Backup preservado; arquivo nao foi salvo."
    )

# Validar antes de gravar.
compile(codigo, str(arquivo), "exec")
arquivo.write_text(codigo, encoding="utf-8")
py_compile.compile(str(arquivo), doraise=True)

print("\nCORRECAO CONCLUIDA!")
print("Ciclo de rolagem removido: OK")
print("Auto-rolagem condicional: OK")
print("Leitura do historico sem puxar a tela: OK")
print("Compilacao: OK")
print("Backup:", backup)
