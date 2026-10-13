"""Texto-para-fala (edge-tts + pygame) e reconhecimento de voz.

Desacoplado da UI: em vez de chamar `app.after(...)` diretamente (como no
código original), recebe um callback opcional `on_estado(estado, texto, cor)`
que quem chamar (o `brain.py`) é quem sabe como repassar pra interface.
Isso permite testar/reusar este módulo sem precisar de uma janela Tkinter.
"""

import asyncio
import io
import queue
import re
import threading
import time
from typing import Callable, Optional

import edge_tts
import pygame
import speech_recognition as sr

from . import config, voz_biometria

EstadoCallback = Optional[Callable[[str, str, str], None]]

pygame.mixer.init()
# Compartilhado com o detector de palavra-chave (jarvis/wakeword.py): os dois
# abrem `sr.Microphone()` em threads diferentes, e `pausar()`/`retomar()` lá
# são só um sinal — não garantem que o detector já soltou o dispositivo antes
# do brain.py tentar abrir o microfone de novo. Duas aberturas simultâneas do
# mesmo dispositivo de áudio no Windows costumam estourar um erro esquisito
# do PortAudio (ex: "[Errno -143760546] Invalid error code"). Esse lock
# garante que só uma thread por vez segura o microfone de verdade.
MICROFONE_LOCK = threading.Lock()
_reconhecedor = sr.Recognizer()
# Padrão da lib é 0.8s de silêncio pra considerar a frase encerrada — curto
# demais pra pausas naturais de quem está pensando no meio da fala, cortava
# o áudio antes da pessoa terminar. 1.2s dá mais folga sem deixar a resposta
# perceptivelmente lenta.
_reconhecedor.pause_threshold = 1.2


_QUEBRA_DE_FRASE = re.compile(r"(?<=[.!?;])\s+")


def _dividir_em_frases(texto: str) -> list[str]:
    """Quebra a resposta em frases, pra poder começar a tocar a primeira
    assim que ela fica pronta, sem esperar o áudio da resposta inteira
    terminar de sintetizar (era a maior fonte de demora perceptível entre o
    modelo responder e o J.A.R.V.I.S. começar a falar)."""
    partes = [p.strip() for p in _QUEBRA_DE_FRASE.split(texto.strip())]
    return [p for p in partes if p]


async def _gerar_audio_bytes(texto: str) -> bytes:
    comunicador = edge_tts.Communicate(texto, config.VOZ_TTS, rate=config.TAXA_FALA)
    pedacos = bytearray()
    async for chunk in comunicador.stream():
        if chunk["type"] == "audio":
            pedacos += chunk["data"]
    return bytes(pedacos)


def _gerar_audio_das_frases(
    frases: list[str], fila: "queue.Queue[Optional[bytes]]", evento_interromper: Optional[threading.Event]
) -> None:
    """Roda numa thread à parte: sintetiza cada frase, em ordem, e põe o
    áudio pronto na fila assim que sai — o consumidor (em `falar`) já pode
    tocar a primeira frase enquanto essa thread ainda sintetiza a segunda.
    Sentinela `None` no final da fila avisa que não vem mais nada."""
    loop = asyncio.new_event_loop()
    try:
        for frase in frases:
            if evento_interromper is not None and evento_interromper.is_set():
                break
            try:
                fila.put(loop.run_until_complete(_gerar_audio_bytes(frase)))
            except Exception as e:
                print(f"Erro ao gerar áudio da frase: {e}")
    finally:
        fila.put(None)
        loop.close()


def falar(
    texto: str,
    on_estado: EstadoCallback = None,
    evento_interromper: Optional[threading.Event] = None,
) -> bool:
    """Fala o texto em voz alta. Se `evento_interromper` for passado e for
    setado por fora (ex: o detector de palavra-chave ouvindo "Jarvis" no meio
    da fala), a reprodução para na hora.

    Devolve True se falou até o fim, False se foi interrompido.
    """
    texto_limpo = texto.replace("*", "").replace('"', "").replace("#", "")
    if not texto_limpo.strip():
        return True
    if on_estado:
        on_estado("falando", "[ COMUNICANDO... ]", "#00f0ff")
    interrompido = False
    try:
        if evento_interromper is not None and evento_interromper.is_set():
            return False  # já foi interrompido antes de começar a tocar

        frases = _dividir_em_frases(texto_limpo) or [texto_limpo]
        fila: "queue.Queue[Optional[bytes]]" = queue.Queue()
        threading.Thread(
            target=_gerar_audio_das_frases, args=(frases, fila, evento_interromper), daemon=True
        ).start()

        while True:
            dados_audio = fila.get()
            if dados_audio is None:
                break  # sentinela: acabaram as frases
            if evento_interromper is not None and evento_interromper.is_set():
                interrompido = True
                break

            pygame.mixer.music.load(io.BytesIO(dados_audio), "mp3")
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if evento_interromper is not None and evento_interromper.is_set():
                    pygame.mixer.music.stop()
                    interrompido = True
                    break
                time.sleep(0.05)
            pygame.mixer.music.unload()
            if interrompido:
                break
    except Exception as e:
        print(f"Erro áudio: {e}")
    finally:
        if on_estado:
            on_estado("aguardando", "[ AGUARDANDO... ]", "#00f0ff")
    return not interrompido


def ouvir(
    on_estado: EstadoCallback = None,
    timeout: Optional[float] = None,
    ao_detectar_voz_diferente: Optional[Callable[[], None]] = None,
) -> str:
    """Escuta e transcreve uma frase. Se `timeout` for passado e ninguém
    começar a falar dentro desse tempo, desiste e devolve "" (em vez de
    ficar esperando pra sempre) — usado no "modo de continuação", onde o
    J.A.R.V.I.S. escuta por uma resposta de acompanhamento sem precisar
    ouvir "Jarvis" de novo, mas não pode ficar escutando indefinidamente.

    Se um perfil vocal tiver sido cadastrado (veja `voz_biometria.py` e
    `setup_perfil_vocal.py`), a voz de quem falou é comparada com esse
    perfil antes de transcrever. Se não bater, chama
    `ao_detectar_voz_diferente` (se passado) e devolve "" sem transcrever —
    mesmo efeito de silêncio, mas quem chamou pode usar o callback pra
    responder algo em voz alta. Sem perfil cadastrado, esse passo é pulado
    inteiro e o comportamento é o mesmo de sempre."""
    with MICROFONE_LOCK:
        with sr.Microphone() as fonte_audio:
            if on_estado:
                on_estado("ouvindo", "[ CAPTURANDO ÁUDIO... ]", "#00ff66")
            _reconhecedor.adjust_for_ambient_noise(fonte_audio, duration=0.5)
            try:
                audio = _reconhecedor.listen(fonte_audio, timeout=timeout)
            except sr.WaitTimeoutError:
                return ""
    # Solta o lock antes da verificação de voz/transcrição (chamadas de
    # rede/CPU) — não precisam do microfone, e libera o detector de palavra-
    # chave mais cedo.

    if voz_biometria.verificar(audio.get_wav_data()) is False:
        if ao_detectar_voz_diferente is not None:
            ao_detectar_voz_diferente()
        return ""

    if on_estado:
        on_estado("processando", "[ PROCESSANDO DADOS... ]", "#ffb000")
    try:
        return _reconhecedor.recognize_google(audio, language="pt-BR")
    except Exception:
        return ""
