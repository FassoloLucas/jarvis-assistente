"""Conecta esse PC ao backend do app de celular (fase 5 do projeto mobile),
pra executar comandos de automação vindos do celular remotamente — abrir
programa, ver tela, digitar texto, etc.

Recurso opcional e "à prova de travar sozinho", mesmo padrão de
`voz_biometria.py`/`ar_condicionado.py`: sem `jarvis/data/relay_credentials.json`
cadastrado, `configurado()` devolve False e o resto do J.A.R.V.I.S. roda
normal. `websocket-client`/`requests` só são importados dentro da thread de
conexão, nunca no topo do módulo.

Design consciente: em vez de um sistema de pareamento por QR code/código
(que precisaria de UI nos dois lados — celular pra mostrar, esse módulo pra
digitar — e não dá pra testar de verdade sem o app existindo ainda), o PC
entra como mais um cliente autenticado da MESMA conta usada no app
(login e-mail/senha contra o backend, igual o app faz). É a mesma ideia de
"logar sua própria conta no seu próprio PC" que várias apps de desktop
companion usam. Um pareamento mais amigável pode substituir isso depois
sem mudar o protocolo por baixo (o backend já trata o PC como só mais uma
sessão autenticada).

Reconecta sozinho se a conexão cair (rede instável, backend reiniciando)
— nunca deixa a thread simplesmente morrer.
"""

import json
import threading
import time
from pathlib import Path
from typing import Optional

from . import tools

CAMINHO_CREDENCIAIS = Path(__file__).parent / "data" / "relay_credentials.json"

_thread: Optional[threading.Thread] = None
_rodando = False
_ATRASO_RECONEXAO = 10  # segundos


def configurado() -> bool:
    return CAMINHO_CREDENCIAIS.exists()


def _carregar_credenciais() -> dict:
    return json.loads(CAMINHO_CREDENCIAIS.read_text(encoding="utf-8"))


def _executar_e_responder(mensagem: dict) -> dict:
    """Executa uma ferramenta pedida remotamente usando os MESMOS
    `tools.TOOL_HANDLERS` que o wake-word local já usa — nenhuma automação
    nova, só mais um jeito de disparar a que já existe."""
    nome = mensagem.get("ferramenta")
    argumentos = mensagem.get("argumentos") or {}
    handler = tools.TOOL_HANDLERS.get(nome)
    if handler is None:
        resultado = f"Ferramenta '{nome}' não existe."
    else:
        try:
            resultado = handler(argumentos).get("resultado", "ok")
        except Exception as e:
            resultado = f"Falha ao executar {nome}: {e}"
    return {"id_requisicao": mensagem.get("id_requisicao"), "resultado": resultado}


def _loop_conexao(url_backend: str, email: str, senha: str) -> None:
    import requests
    import websocket  # pacote "websocket-client"

    while _rodando:
        try:
            resposta = requests.post(f"{url_backend}/login", json={"email": email, "senha": senha}, timeout=10)
            resposta.raise_for_status()
            token = resposta.json()["token"]

            url_ws = url_backend.replace("https://", "wss://", 1).replace("http://", "ws://", 1)
            ws = websocket.create_connection(f"{url_ws}/pc/conectar?token={token}", timeout=10)
            # O timeout acima é só pra ESTABELECER a conexão — sem resetar,
            # ele também valeria pro recv() de espera logo abaixo, e como
            # não há tráfego nenhum enquanto nenhum comando chega, isso
            # causava reconexões falsas a cada ~10s (recv() estourando
            # timeout, sendo tratado como queda de conexão). None = espera
            # bloqueada de verdade até chegar mensagem ou a conexão cair.
            ws.settimeout(None)
            print("[relay] Conectado ao backend — PC disponível pro app de celular.")

            while _rodando:
                mensagem_bruta = ws.recv()
                if not mensagem_bruta:
                    break  # conexão fechada do outro lado
                mensagem = json.loads(mensagem_bruta)
                ws.send(json.dumps(_executar_e_responder(mensagem)))
        except Exception as e:
            if not _rodando:
                break
            print(f"[relay] Conexão com o backend caiu ({e}); tentando de novo em {_ATRASO_RECONEXAO}s...")
            time.sleep(_ATRASO_RECONEXAO)


def iniciar() -> None:
    """Sobe a thread de conexão, se configurado e ainda não estiver
    rodando. Chamado uma vez no boot (veja main.py) — não faz nada se
    `relay_credentials.json` não existir."""
    global _thread, _rodando
    if not configurado() or _rodando:
        return
    dados = _carregar_credenciais()
    _rodando = True
    _thread = threading.Thread(
        target=_loop_conexao,
        args=(dados["url_backend"], dados["email"], dados["senha"]),
        daemon=True,
    )
    _thread.start()


def parar() -> None:
    global _rodando
    _rodando = False
