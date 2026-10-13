"""Detecção da palavra de ativação ("Jarvis"), via reconhecimento de voz.

Usa o mesmo mecanismo do resto do projeto (`speech_recognition` + Google) em
vez de um detector 100% local — decisão consciente pra não depender de conta
em nenhum serviço novo. O trade-off: roda em rajadas curtas (até
`config.TEMPO_MAX_RAJADA_WAKE` segundos) numa thread própria, e cada rajada
é enviada pro Google pra transcrever — mesmo quando não é "Jarvis", ela é só
descartada depois. Ou seja: ainda sai áudio da máquina continuamente,
diferente de um detector local de verdade (esse foi o trade-off aceito no
lugar de precisar de uma conta na Picovoice).

A interface (`iniciar`/`pausar`/`retomar`/`parar`) é a mesma que `brain.py`
já espera, então o resto da orquestração não precisou mudar.
"""

import threading
import time

import speech_recognition as sr

from . import config
from .audio import MICROFONE_LOCK


class DetectorPalavraChave:
    def __init__(self, on_deteccao):
        self._on_deteccao = on_deteccao
        self._reconhecedor = sr.Recognizer()
        self._microfone = sr.Microphone()
        self._ambiente_ajustado = False
        self._thread = None
        self._rodando = False
        self._pausado = threading.Event()
        self._pausado.set()  # começa pausado; iniciar() libera

    def _capturar_rajada(self):
        """Abre o microfone só pelo tempo da escuta e libera em seguida —
        assim o dispositivo fica de fato livre enquanto pausado (necessário
        pro `speech_recognition` conseguir capturar o comando de verdade
        sem disputar o mesmo microfone).

        `pausar()`/`retomar()` (Event) só sinalizam intenção — não travam o
        microfone de verdade. Quem garante isso é `MICROFONE_LOCK`
        (compartilhado com `audio.ouvir`): sem essa exclusão, as duas threads
        podiam abrir o mesmo dispositivo ao mesmo tempo e o PortAudio
        estourava um erro esquisito (ex: "[Errno -143760546] Invalid error
        code"). `acquire(timeout=...)` em vez de bloquear pra sempre, pra não
        travar essa thread se o brain.py estiver com o microfone.
        """
        if not MICROFONE_LOCK.acquire(timeout=0.3):
            return None  # microfone ocupado agora — tenta de novo no próximo ciclo
        try:
            with self._microfone as fonte:
                if not self._ambiente_ajustado:
                    self._reconhecedor.adjust_for_ambient_noise(fonte, duration=0.5)
                    self._ambiente_ajustado = True
                # timeout curto: se ninguém falar nada, desiste rápido e volta
                # pro loop pra checar se foi pedido pra pausar/parar.
                return self._reconhecedor.listen(
                    fonte, timeout=1.5, phrase_time_limit=config.TEMPO_MAX_RAJADA_WAKE
                )
        finally:
            MICROFONE_LOCK.release()

    def _loop(self):
        while self._rodando:
            if self._pausado.is_set():
                time.sleep(0.1)
                continue

            try:
                audio_capturado = self._capturar_rajada()
            except sr.WaitTimeoutError:
                continue
            except Exception as e:
                print(f"Erro ao capturar áudio no detector de palavra-chave: {e}")
                time.sleep(0.2)
                continue

            if audio_capturado is None:
                continue  # microfone estava ocupado (ver _capturar_rajada)

            if self._pausado.is_set() or not self._rodando:
                continue  # foi pausado/parado enquanto processava; descarta

            try:
                texto = self._reconhecedor.recognize_google(audio_capturado, language="pt-BR")
            except Exception:
                continue  # silêncio/ruído/erro de rede — ignora e continua ouvindo

            if config.PALAVRA_CHAVE in texto.lower():
                self._on_deteccao()

    def iniciar(self):
        self._rodando = True
        self._pausado.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def pausar(self):
        """Sinaliza pra thread liberar o microfone (ela termina a rajada
        atual, se houver, e não abre outra até `retomar()`)."""
        self._pausado.set()

    def retomar(self):
        self._pausado.clear()

    def parar(self):
        self._rodando = False
        self._pausado.set()
