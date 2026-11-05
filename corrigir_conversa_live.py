from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys

arquivo = Path("modulos/conversa_ao_vivo.py")

if not arquivo.exists():
    raise SystemExit("ERRO: modulo de conversa ao vivo nao encontrado.")

codigo = arquivo.read_text(encoding="utf-8-sig")

backup = Path(
    "modulos/conversa_ao_vivo.backup_"
    + datetime.now().strftime("%Y%m%d_%H%M%S")
    + ".py"
)
shutil.copy2(arquivo, backup)


def substituir_regiao(texto, inicio, fim, novo, descricao):
    a = texto.find(inicio)
    if a < 0:
        raise RuntimeError("Nao encontrei o inicio de: " + descricao)

    b = texto.find(fim, a + len(inicio))
    if b < 0:
        raise RuntimeError("Nao encontrei o fim de: " + descricao)

    return texto[:a] + novo.rstrip() + "\n\n" + texto[b:]


# Guardar o identificador de retomada da sessao.
if "self._resume_handle = None" not in codigo:
    marcador = "        self.input_device = input_device"
    if marcador not in codigo:
        raise RuntimeError("Nao encontrei a inicializacao do dispositivo.")
    codigo = codigo.replace(
        marcador,
        marcador + "\n        self._resume_handle = None",
        1
    )

# Receber novamente apos cada turno, sem encerrar a conversa.
novo_receive = r'''
    async def receive_messages(self, session):
        user_text = ""
        assistant_text = ""

        while not self._stop_event.is_set():
            recebeu_mensagem = False

            try:
                async for message in session.receive():
                    recebeu_mensagem = True

                    if self._stop_event.is_set():
                        break

                    update = getattr(
                        message, "session_resumption_update", None
                    )

                    if update is not None:
                        if (
                            getattr(update, "resumable", False)
                            and getattr(update, "new_handle", None)
                        ):
                            self._resume_handle = update.new_handle

                    if getattr(message, "go_away", None) is not None:
                        self.status.emit("PREPARANDO RECONEXAO")

                    content = getattr(message, "server_content", None)

                    if content is None:
                        continue

                    if getattr(content, "interrupted", False):
                        self.clear_playback()
                        self.save_turn(user_text, assistant_text)
                        user_text = ""
                        assistant_text = ""

                    input_transcript = getattr(
                        content, "input_transcription", None
                    )

                    if input_transcript:
                        user_text = self.merge_transcript(
                            user_text,
                            getattr(input_transcript, "text", "")
                        )

                    output_transcript = getattr(
                        content, "output_transcription", None
                    )

                    if output_transcript:
                        assistant_text = self.merge_transcript(
                            assistant_text,
                            getattr(output_transcript, "text", "")
                        )

                    model_turn = getattr(content, "model_turn", None)

                    if model_turn:
                        for part in model_turn.parts:
                            inline = getattr(part, "inline_data", None)

                            if inline and inline.data:
                                raw = bytes(inline.data)

                                try:
                                    self._play_queue.put_nowait(raw)
                                except queue.Full:
                                    pass

                                samples = np.frombuffer(
                                    raw, dtype="<i2"
                                )

                                if samples.size:
                                    rms = float(
                                        np.sqrt(
                                            np.mean(
                                                samples.astype(np.float32) ** 2
                                            )
                                        )
                                    ) / 32768.0

                                    self.audio_level.emit(
                                        min(1.0, rms * 8.0)
                                    )

                    if getattr(content, "turn_complete", False):
                        self.save_turn(user_text, assistant_text)
                        user_text = ""
                        assistant_text = ""
                        self.audio_level.emit(0.0)

                # O SDK encerra receive() ao concluir um turno.
                # Chamamos novamente para continuar ouvindo a mesma sessao.
                if not recebeu_mensagem and not self._stop_event.is_set():
                    await asyncio.sleep(0.05)

            except asyncio.CancelledError:
                raise

            except Exception:
                self.save_turn(user_text, assistant_text)
                raise
'''

codigo = substituir_regiao(
    codigo,
    "    async def receive_messages(self, session):",
    "    async def run_session(self):",
    novo_receive,
    "receive_messages"
)

# Habilitar retomada de sessao e compressao de contexto.
marcador_config = '            "response_modalities": ["AUDIO"],'

if '"session_resumption"' not in codigo:
    if marcador_config not in codigo:
        raise RuntimeError("Nao encontrei a configuracao de audio.")
    codigo = codigo.replace(
        marcador_config,
        marcador_config
        + '\n            "session_resumption": {"handle": self._resume_handle},'
        + '\n            "context_window_compression": {"sliding_window": {}},',
        1
    )

# Reconectar quando a rede ou o servidor interromperem a conexao.
novo_run = r'''
    def run(self):
        tentativa = 0

        try:
            while not self._stop_event.is_set():
                try:
                    asyncio.run(self.run_session())

                    if self._stop_event.is_set():
                        break

                    raise ConnectionError(
                        "Conexao Live encerrada inesperadamente."
                    )

                except Exception as exc:
                    if self._stop_event.is_set():
                        break

                    mensagem = f"{type(exc).__name__}: {exc}"
                    inferior = mensagem.lower()

                    # Se o token de retomada estiver invalido,
                    # tentar uma sessao nova uma vez.
                    if self._resume_handle and (
                        "400" in inferior or "invalid" in inferior
                        or "resume" in inferior
                    ):
                        print(
                            "[JARVIS LIVE] Token de retomada recusado. "
                            "Tentando uma sessao nova."
                        )
                        self._resume_handle = None
                        tentativa = 0
                        self.status.emit("REINICIANDO SESSAO")
                        self._stop_event.wait(1)
                        continue

                    erros_fatais = (
                        "401",
                        "403",
                        "404",
                        "unauthorized",
                        "permission_denied",
                        "api key not valid",
                        "model not found",
                        "invalid_argument",
                    )

                    if any(item in inferior for item in erros_fatais):
                        self.error.emit(
                            "Nao foi possivel manter a conexao Live. "
                            + mensagem[:350]
                        )
                        break

                    tentativa += 1
                    espera = min(30, 2 ** min(tentativa, 5))

                    print(
                        f"[JARVIS LIVE] {mensagem[:250]} "
                        f"| Nova tentativa em {espera}s"
                    )

                    self.status.emit(
                        f"CONEXAO INSTAVEL - RECONEXAO EM {espera}s"
                    )

                    self._stop_event.wait(espera)

        finally:
            self.clear_playback()
            self.status.emit("MODO AO VIVO ENCERRADO")
'''

inicio_run = codigo.rfind("    def run(self):")
if inicio_run < 0:
    raise RuntimeError("Nao encontrei o metodo run.")

codigo = codigo[:inicio_run] + novo_run.rstrip() + "\n"

arquivo.write_text(codigo, encoding="utf-8")

py_compile.compile(str(arquivo), doraise=True)

sys.path.insert(0, str(Path.cwd()))
from modulos.conversa_ao_vivo import LiveVoiceWorker

print("COMPILACAO: OK")
print("IMPORTACAO: OK")
print("ESCUTA ENTRE TURNOS: ATIVA")
print("RECONEXAO AUTOMATICA: CONFIGURADA")
print("RETOMADA DE SESSAO: CONFIGURADA")
print("VOZ: Algenib (preservada)")
print("BACKUP:", backup)
print("\nATUALIZACAO CONCLUIDA.")
