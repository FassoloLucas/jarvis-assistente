"""Orquestração: rotina de inicialização e loop principal do J.A.R.V.I.S.

O núcleo da mudança das ações está em `processar_comando` / `_executar_tool_calls`:
em vez de mandar o comando pro modelo e depois vasculhar o texto de volta
procurando substrings tipo "[SITE]" (frágil — ver comentários em
`tools.py`), o comando é enviado junto com o catálogo de ferramentas
(`tools.TOOLS`) e é o próprio modelo que decide, de forma estruturada, se
vai responder em texto ou chamar uma ou mais ferramentas.

A conversa em si agora é travada pela palavra de ativação (veja
`wakeword.py`): o J.A.R.V.I.S. fica em silêncio, sem mandar nada pra
internet, até ouvir "Jarvis" localmente. Só então ele confirma em voz alta
e passa a escutar o comando de verdade — aí sim via `speech_recognition`
(Google), só pro comando em si, não o tempo todo. Dizer "Jarvis" enquanto
ele está falando também interrompe a fala na hora: o mesmo evento
(`_wake_event`) serve tanto pra "acordar" quanto pra "calar a boca e ouvir
de novo".
"""

import json
import threading
from datetime import datetime

from openai import OpenAI

from . import config, tools, web
from .audio import falar, ouvir
from .persona import montar_system_prompt
from .tempo import agora_por_extenso
from .wakeword import DetectorPalavraChave

client = OpenAI(api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL)

SYSTEM_PROMPT = montar_system_prompt()

PALAVRAS_POSITIVAS = ["sim", "quero", "pode", "claro", "manda", "uhum", "por favor"]


class Cerebro:
    """Mantém o histórico da conversa e conduz o loop travado por wake word."""

    def __init__(self, app):
        self.app = app
        self.historico = [{"role": "system", "content": SYSTEM_PROMPT}]
        # Setado pelo detector (jarvis/wakeword.py) sempre que "Jarvis" é
        # ouvido — tanto em silêncio quanto no meio de uma fala/execução.
        self._wake_event = threading.Event()
        self._detector = DetectorPalavraChave(on_deteccao=self._wake_event.set)
        # A frase de ativação ("Pois não, senhor...") só faz sentido na
        # primeira vez que ele acorda na sessão — depois disso, ir direto
        # pra escuta deixa a conversa mais fluida.
        self._ja_ativou = False

    # --- Auxiliares de UI/áudio ---
    def _estado(self, estado, texto, cor):
        self.app.after(0, self.app.mudar_estado, estado, texto, cor)

    def _falar(self, texto):
        """Fala e devolve True se falou até o fim (False se foi cortado por
        "Jarvis" no meio)."""
        if not texto:
            return True
        return falar(texto, on_estado=self._estado, evento_interromper=self._wake_event)

    def _ouvir(self, timeout=None):
        # O detector de palavra-chave e o speech_recognition disputam o
        # mesmo microfone — libera um pro outro.
        self._detector.pausar()
        try:
            return ouvir(
                on_estado=self._estado,
                timeout=timeout,
                # Só entra em ação se um perfil vocal tiver sido cadastrado
                # (veja voz_biometria.py) — sem isso, é ignorado.
                ao_detectar_voz_diferente=lambda: self._falar(
                    "Essa não é a voz do meu chefe. Não vou executar esse comando."
                ),
            )
        finally:
            self._detector.retomar()

    def _perguntar_ia(self, mensagens, usar_tools=True):
        return client.chat.completions.create(
            model=config.MODEL_ID,
            messages=mensagens,
            tools=tools.TOOLS if usar_tools else None,
            temperature=config.TEMPERATURE,
        )

    # --- Rotina de boas-vindas (roda uma vez, antes do detector subir) ---
    def rotina_inicializacao(self):
        hora_atual = datetime.now().hour
        saudacao = "Bom dia" if hora_atual < 12 else "Boa tarde" if hora_atual < 18 else "Boa noite"
        self._falar(f"{saudacao}, chefe! Um momento, vou verificar o clima e as condições do dia para o senhor.")

        self._estado("processando", "[ ACESSANDO SATÉLITES... ]", "#ffb000")
        clima_info = web.buscar_na_internet(f"clima em {config.CIDADE_CLIMA_LABEL}")
        try:
            resposta = self._perguntar_ia(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Diga de forma rápida e fluida como está o clima agora: '{clima_info}'"},
                ],
                usar_tools=False,
            )
            self._falar(resposta.choices[0].message.content)
        except Exception:
            self._falar("Os satélites estão instáveis, mas o sistema está operando.")

        self._falar("O senhor tem interesse em saber das notícias do dia?")
        resposta_usuario = (ouvir(on_estado=self._estado, timeout=config.TIMEOUT_CONTINUACAO) or "").lower()

        if resposta_usuario and any(p in resposta_usuario for p in PALAVRAS_POSITIVAS):
            self._falar("Beleza, vou olhar as principais notícias.")
            self._estado("processando", "[ CONSULTANDO FEED RSS... ]", "#ffb000")
            noticia_info = web.buscar_na_internet("infomoney economia")
            try:
                resposta = self._perguntar_ia(
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": f"Resuma rapidamente estas manchetes: '{noticia_info}'"},
                    ],
                    usar_tools=False,
                )
                self._falar(resposta.choices[0].message.content)
            except Exception:
                self._falar("As redes de notícias estão bloqueadas no momento, senhor.")
        else:
            self._falar("Tudo bem, estou aqui se precisar.")

    # --- Execução das ferramentas pedidas pelo modelo ---
    def _executar_tool_calls(self, mensagem_ia, mensagens):
        mensagens.append(mensagem_ia)
        imagem_capturada = None
        memoria_mudou = False

        for chamada in mensagem_ia.tool_calls:
            if self._wake_event.is_set():
                break  # foi interrompido: para de encadear ações e volta a ouvir

            nome = chamada.function.name
            try:
                argumentos = json.loads(chamada.function.arguments or "{}")
            except json.JSONDecodeError:
                argumentos = {}

            handler = tools.TOOL_HANDLERS.get(nome)
            if handler is None:
                mensagens.append({"role": "tool", "tool_call_id": chamada.id, "content": f"Ferramenta '{nome}' não existe."})
                continue

            self._estado("processando", f"[ EXECUTANDO: {nome.upper()} ]", "#ffb000")
            try:
                saida = handler(argumentos)
            except Exception as e:
                mensagens.append({"role": "tool", "tool_call_id": chamada.id, "content": f"Falha ao executar {nome}: {e}"})
                continue

            if nome in tools.FERRAMENTAS_QUE_MUDAM_MEMORIA:
                memoria_mudou = True

            self._falar(saida.get("fala"))
            if saida.get("imagem"):
                imagem_capturada = saida["imagem"]

            mensagens.append({"role": "tool", "tool_call_id": chamada.id, "content": saida.get("resultado", "ok")})

        if memoria_mudou:
            # Recarrega o system prompt (que injeta a memória aprendida) na
            # hora, pra já valer dentro da mesma conversa — sem precisar
            # reiniciar o programa pra um fato novo entrar em vigor.
            mensagem_sistema_atualizada = {"role": "system", "content": montar_system_prompt()}
            self.historico[0] = mensagem_sistema_atualizada
            mensagens[0] = mensagem_sistema_atualizada

        if imagem_capturada:
            # Tool messages geralmente só aceitam conteúdo em texto — a imagem
            # entra como um novo turno de usuário logo em seguida, pra o
            # modelo poder efetivamente "ver" a captura de tela.
            mensagens.append(
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Aqui está a captura de tela que você pediu. Continue a partir daqui."},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{imagem_capturada}"}},
                    ],
                }
            )

        return mensagens

    # --- Processamento de um comando falado ---
    def processar_comando(self, comando_usuario: str):
        self.historico.append({"role": "user", "content": comando_usuario})
        mensagens = self.historico.copy()

        # Data/hora atual injetada fresca a cada chamada (não guardada no
        # histórico) — assim o modelo sempre sabe "agora" de verdade, mesmo
        # numa sessão que já está rodando há horas, e consegue calcular
        # datas relativas ("amanhã", "sexta que vem") sozinho.
        mensagens.insert(1, {"role": "system", "content": f"Data e hora atuais: {agora_por_extenso()}."})

        self._estado("processando", "[ SINCRONIZANDO REDE NEURAL... ]", "#ffb000")

        for _ in range(config.MAX_RODADAS_TOOL_CALLING):
            if self._wake_event.is_set():
                return  # "Jarvis" no meio do processamento: aborta e volta pro loop principal

            resposta = self._perguntar_ia(mensagens)
            mensagem_ia = resposta.choices[0].message

            if mensagem_ia.tool_calls:
                mensagens = self._executar_tool_calls(mensagem_ia, mensagens)
                continue

            texto_resposta = mensagem_ia.content or ""
            self.historico.append({"role": "assistant", "content": texto_resposta})
            self._falar(texto_resposta)
            return texto_resposta

        self._falar("Me perdi numa sequência de ações, chefe. Pode repetir o pedido?")
        return None

    def _desligar(self):
        self._falar("Desligando todos os protocolos. Até logo, chefe.")
        self._detector.parar()
        self.app.after(1000, self.app.destroy)

    def _tratar_comando(self, comando_usuario: str) -> bool:
        """Processa um comando e, depois de responder, mantém escutando
        direto — sem precisar ouvir "Jarvis" de novo — até o chefe ficar em
        silêncio por `TIMEOUT_CONTINUACAO` ou pedir pra desligar. Antes só
        continuava se a resposta terminasse em "?" (heurística frágil,
        dependia de como o modelo formulava a frase); agora a conversa flui
        depois de qualquer resposta, e quem decide quando parar é o
        silêncio do chefe, não a pontuação do modelo. Devolve True se um
        desligamento foi pedido (pro `loop()` saber que deve encerrar)."""
        while True:
            if "desligar sistema" in comando_usuario.lower():
                self._desligar()
                return True

            self.processar_comando(comando_usuario)

            if self._wake_event.is_set():
                return False  # interrompido: o loop principal já reengaja sozinho

            self._estado("ouvindo", "[ AGUARDANDO CONTINUAÇÃO... ]", "#00ff66")
            proximo_comando = self._ouvir(timeout=config.TIMEOUT_CONTINUACAO)
            if not proximo_comando:
                return False  # silêncio: volta a exigir "Jarvis"

            comando_usuario = proximo_comando

    # --- Loop principal, travado pela palavra de ativação ---
    def loop(self):
        self.rotina_inicializacao()
        self._detector.iniciar()

        while True:
            self._estado("aguardando", "[ AGUARDANDO 'JARVIS'... ]", "#00f0ff")
            self._wake_event.wait()  # só desbloqueia quando "Jarvis" é detectado
            self._wake_event.clear()

            try:
                if not self._ja_ativou:
                    self._falar(config.FRASE_ATIVACAO)
                    self._ja_ativou = True
                    if self._wake_event.is_set():
                        continue  # foi chamado de novo antes de terminar de falar — reinicia o ciclo

                comando_usuario = self._ouvir()
                if not comando_usuario:
                    continue

                if self._tratar_comando(comando_usuario):
                    break
            except Exception as e:
                print(f"Erro: {e}")
                self._falar("Houve uma falha momentânea de comunicação com os servidores centrais.")
