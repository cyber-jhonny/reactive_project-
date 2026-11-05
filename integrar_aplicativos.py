from pathlib import Path
import shutil

p = Path("interface.py")
s = p.read_text(encoding="utf-8-sig")

# Verificações para evitar alterações duplicadas ou incorretas.
if "from modulos.aplicativos import detectar_comando, abrir_aplicativos" in s:
    raise SystemExit("O modulo de aplicativos ja esta integrado.")

import_marker = "from modulos.inteligencia import conversar"
memory_marker = "from modulos.memoria import ("
process_marker = '''            self.stop_event.set()
            return

        self.status.emit("PENSANDO...")'''

if s.count(import_marker) != 1:
    raise SystemExit("Importacao da inteligencia nao encontrada.")

if s.count(memory_marker) != 1:
    raise SystemExit("Bloco de importacao da memoria nao encontrado.")

if s.count(process_marker) != 1:
    raise SystemExit("Ponto de integracao do processamento nao encontrado.")

if not Path("modulos/aplicativos.py").is_file():
    raise SystemExit("modulos/aplicativos.py nao encontrado.")

# Preservar a versao atual.
backup = Path("interface_backup_integracao_apps.py")
if not backup.exists():
    shutil.copy2(p, backup)

# Importar os novos recursos.
s = s.replace(
    import_marker,
    import_marker
    + "\nfrom modulos.aplicativos import detectar_comando, abrir_aplicativos"
    + "\nfrom modulos.memoria import salvar_mensagem",
    1
)

# Executar comandos autorizados antes de consultar a inteligencia.
bloco = '''            self.stop_event.set()
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

        self.status.emit("PENSANDO...")'''

s = s.replace(process_marker, bloco, 1)

p.write_text(s, encoding="utf-8")

print("INTEGRACAO CONCLUIDA!")
print("Comandos de aplicativos conectados ao JARVIS.")
print("Historico e resposta por voz preservados.")
print("Backup: interface_backup_integracao_apps.py")
