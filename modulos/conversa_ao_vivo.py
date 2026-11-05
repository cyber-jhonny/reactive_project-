
import asyncio
import os
import queue
import threading

import numpy as np
import sounddevice as sd
from scipy.signal import resample_poly

from PySide6.QtCore import QThread, Signal
from dotenv import load_dotenv
from google import genai
from google.genai import types

from modulos.caminhos import ENV_FILE

from modulos.memoria import (
    consultar_memorias,
    historico_recente,
    salvar_mensagem,
)

from modulos.memoria_contextual import contexto_inicial, buscar_historico_antigo
from modulos.live_tools import TOOL_DECLARATIONS, executar_ferramenta

LIVE_MODEL = "gemini-3.8-live"
INPUT_RATE = 44100
LIVE_INPUT_RATE = 16000
OUTPUT_RATE = 24000
INPUT_BLOCK = 4410


class LiveVoiceWorker(QThread):

    status = Signal(str)
    transcription = Signal(str)
    response = Signal(str)
    audio_level = Signal(float)
    error = Signal(str)
    conversation_changed = Signal()

    def __init__(self, conversation_id=None, input_device=1):
        super().__init__()

        self._stop_event = threading.Event()
        self._conversation_lock = threading.Lock()
        self._conversation_id = conversation_id
        self.input_device = input_device
        self._resume_handle = None

        self._play_queue = queue.Queue(maxsize=160)
        self._play_lock = threading.Lock()
        self._play_state = {
            "samples": np.empty(0, dtype=np.int16),
            "offset": 0,
        }

    def stop(self):
        self._stop_event.set()

    def set_conversation(self, conversation_id):
        with self._conversation_lock:
            self._conversation_id = conversation_id

    def get_conversation(self):
        with self._conversation_lock:
            return self._conversation_id

    @staticmethod
    def merge_transcript(current, new_text):
        new_text = (new_text or "").strip()

        if not new_text:
            return current

        if not current:
            return new_text

        if new_text.startswith(current):
            return new_text

        if current.startswith(new_text) or current.endswith(new_text):
            return current

        return current + " " + new_text

    def clear_playback(self):
        with self._play_lock:
            while True:
                try:
                    self._play_queue.get_nowait()
                except queue.Empty:
                    break

            self._play_state["samples"] = np.empty(0, dtype=np.int16)
            self._play_state["offset"] = 0

        self.audio_level.emit(0.0)

    def output_callback(self, outdata, frames, time_info, status):
        outdata.fill(0)

        with self._play_lock:
            position = 0

            while position < frames:
                samples = self._play_state["samples"]
                offset = self._play_state["offset"]

                if offset >= len(samples):
                    try:
                        raw = self._play_queue.get_nowait()
                    except queue.Empty:
                        break

                    samples = np.frombuffer(raw, dtype="<i2")

                    if samples.size == 0:
                        continue

                    self._play_state["samples"] = samples
                    self._play_state["offset"] = 0
                    offset = 0

                available = len(samples) - offset
                count = min(frames - position, available)

                outdata[position:position + count, 0] = (
                    samples[offset:offset + count]
                )

                position += count
                self._play_state["offset"] = offset + count

    def save_turn(self, user_text, assistant_text):
        conversation_id = self.get_conversation()

        try:
            if user_text:
                self.transcription.emit(user_text)
                salvar_mensagem("user", user_text, conversation_id)

            if assistant_text:
                self.response.emit(assistant_text)
                salvar_mensagem("assistant", assistant_text, conversation_id)

            if user_text or assistant_text:
                self.conversation_changed.emit()

        except Exception as exc:
            self.error.emit("Falha ao salvar a conversa: " + str(exc))

    def build_instructions(self):
        parts = [
            "Voce e JARVIS, um assistente pessoal inteligente.",
            "Fale sempre em portugues brasileiro.",
            "Converse naturalmente e seja objetivo.",
            "Voce possui ferramentas para abrir aplicativos, pesquisar "
            "na internet, consultar noticias e clima, ler paginas e "
            "recuperar memorias antigas.",
            "Voce tambem pode pesquisar o catalogo local de aplicativos "
            "instalados no Windows.",
            "Quando o usuario pedir para abrir um aplicativo cujo nome "
            "voce nao conhece, primeiro use buscar_aplicativos_instalados. "
            "Depois escolha a correspondencia correta e use abrir_aplicativo.",
            "Se houver mais de uma correspondencia plausivel, pergunte "
            "qual delas o usuario deseja abrir.",
            "Em missoes com varias etapas, monte um plano curto, execute "
            "as etapas na ordem, confira o resultado de cada ferramenta "
            "e depois prossiga.",
            "Nao afirme que uma tarefa foi concluida sem receber resultado "
            "positivo da ferramenta.",
            "Voce tem autonomia avancada, mas iniciativa somente autorizada: "
            "nao comece tarefas por conta propria nem realize acoes que "
            "o usuario nao solicitou.",
            "Abrir aplicativos e sites pode ser feito quando solicitado "
            "explicitamente pelo usuario.",
            "Downloads exigem duas etapas: preparar o download, informar "
            "o usuario e aguardar a frase explicita 'confirmar download'. "
            "Nunca chame confirmar_download por inferencia, silencio ou "
            "uma resposta vaga como 'sim'.",
            "Nunca execute comandos arbitrarios de terminal, scripts, "
            "arquivos executaveis desconhecidos ou alteracoes administrativas.",
            "Nao envie arquivos locais, senhas, tokens ou dados privados "
            "para a internet.",
            "Use buscar_historico_antigo quando uma pergunta depender "
            "de conversas anteriores ou de projetos antigos.",
            "Nao invente lembrancas, resultados ou acoes.",
            "O usuario pode interromper sua fala a qualquer momento."
        ]

        try:
            contexto = contexto_inicial(
                conversation_id=self.get_conversation(),
                limite_mensagens=14
            )

            if contexto:
                parts.append(
                    "\nCONTEXTO RECUPERADO DO BANCO SQLITE:\n" + contexto
                )

        except Exception as exc:
            print("[MEMORIA LIVE]", str(exc)[:200])

        return "\n\n".join(parts)

    async def send_audio(self, session, audio_queue):
        while not self._stop_event.is_set():
            try:
                chunk = await asyncio.wait_for(
                    audio_queue.get(),
                    timeout=0.2
                )
            except asyncio.TimeoutError:
                continue

            await session.send_realtime_input(
                audio=types.Blob(
                    data=chunk,
                    mime_type="audio/pcm;rate=16000"
                )
            )

    async def receive_messages(self, session):
        user_text = ""
        assistant_text = ""

        while not self._stop_event.is_set():
            recebeu_mensagem = False

            try:
                async for message in session.receive():
                    tool_call = getattr(message, "tool_call", None)

                    if tool_call:
                        function_responses = []

                        for fc in (getattr(tool_call, "function_calls", None) or []):
                            nome = getattr(fc, "name", "")
                            argumentos = getattr(fc, "args", {}) or {}

                            try:
                                resultado = executar_ferramenta(
                                    nome,
                                    argumentos,
                                    texto_usuario=user_text
                                )
                            except Exception as exc:
                                resultado = (
                                    f"Erro interno ao executar {nome}: "
                                    f"{type(exc).__name__}: {exc}"
                                )

                            if not isinstance(resultado, str):
                                resultado = str(resultado)

                            function_responses.append(
                                types.FunctionResponse(
                                    id=fc.id,
                                    name=nome,
                                    response={"resultado": resultado[:12000]}
                                )
                            )

                        if function_responses:
                            await session.send_tool_response(
                                function_responses=function_responses
                            )

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

                if not recebeu_mensagem and not self._stop_event.is_set():
                    await asyncio.sleep(0.05)

            except asyncio.CancelledError:
                raise

            except Exception:
                self.save_turn(user_text, assistant_text)
                raise

    async def run_session(self):
        load_dotenv(ENV_FILE)

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise RuntimeError(
                f"GEMINI_API_KEY nao encontrada no arquivo {ENV_FILE}"
            )

        client = genai.Client(
            api_key=api_key,
            http_options={
                "api_version": "v1beta",
                "timeout": 30000,
            }
        )

        config = {
            "response_modalities": ["AUDIO"],

            "tools": [{"function_declarations": TOOL_DECLARATIONS}],

            "session_resumption": {"handle": self._resume_handle},
            "context_window_compression": {"sliding_window": {}},
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "system_instruction": self.build_instructions(),
            "speech_config": {
                "voice_config": {
                    "prebuilt_voice_config": {
                        "voice_name": "Algenib"
                    }
                }
            }
        }

        self.status.emit("CONECTANDO GEMINI LIVE")

        async with client.aio.live.connect(
            model=LIVE_MODEL,
            config=config
        ) as session:

            loop = asyncio.get_running_loop()
            audio_queue = asyncio.Queue(maxsize=30)

            def enqueue_audio(data):
                if audio_queue.full():
                    try:
                        audio_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        pass

                try:
                    audio_queue.put_nowait(data)
                except asyncio.QueueFull:
                    pass

            def input_callback(indata, frames, time_info, status):
                if self._stop_event.is_set():
                    return

                try:
                    mono = indata[:, 0]

                    converted = resample_poly(
                        mono,
                        160,
                        441
                    )

                    pcm = (
                        np.clip(converted, -1.0, 1.0) * 32767
                    ).astype("<i2").tobytes()

                    loop.call_soon_threadsafe(
                        enqueue_audio,
                        pcm
                    )

                except Exception:
                    pass

            self.status.emit("CONVERSA AO VIVO")

            with sd.OutputStream(
                samplerate=OUTPUT_RATE,
                channels=1,
                dtype="int16",
                callback=self.output_callback,
                blocksize=0,
            ):
                with sd.InputStream(
                    device=self.input_device,
                    samplerate=INPUT_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=INPUT_BLOCK,
                    callback=input_callback,
                ):
                    sender = asyncio.create_task(
                        self.send_audio(session, audio_queue)
                    )

                    receiver = asyncio.create_task(
                        self.receive_messages(session)
                    )

                    tasks = [sender, receiver]

                    while not self._stop_event.is_set():
                        done, _ = await asyncio.wait(
                            tasks,
                            timeout=0.2,
                            return_when=asyncio.FIRST_COMPLETED
                        )

                        if done:
                            for task in done:
                                if task.cancelled():
                                    continue

                                exception = task.exception()
                                if exception:
                                    raise exception

                            break

                    for task in tasks:
                        if not task.done():
                            task.cancel()

                    await asyncio.gather(
                        *tasks,
                        return_exceptions=True
                    )

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
