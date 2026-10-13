"""Registro de agentes PC conectados via WebSocket — permite ao backend
relayar uma chamada de ferramenta pro PC de um usuário específico e esperar
o resultado, mesmo com o PC atrás do NAT de casa (ele é quem conecta pra
fora; o backend nunca precisa alcançar o PC diretamente).

Casamento requisição/resposta por `id_requisicao` (um `asyncio.Future` por
requisição pendente) — necessário porque é uma única conexão WebSocket de
longa duração por usuário, não uma requisição HTTP por comando.
"""

import asyncio
import json
import uuid

from fastapi import WebSocket

_conexoes: dict[str, WebSocket] = {}
_pendentes: dict[str, "asyncio.Future"] = {}


def conectado(id_usuario: str) -> bool:
    return id_usuario in _conexoes


def registrar(id_usuario: str, websocket: WebSocket) -> None:
    _conexoes[id_usuario] = websocket


def desregistrar(id_usuario: str) -> None:
    _conexoes.pop(id_usuario, None)


async def escutar_respostas(websocket: WebSocket) -> None:
    """Roda enquanto a conexão do agente estiver aberta, despachando cada
    resposta que chega pro Future correspondente."""
    while True:
        mensagem_bruta = await websocket.receive_text()
        mensagem = json.loads(mensagem_bruta)
        futuro = _pendentes.pop(mensagem.get("id_requisicao"), None)
        if futuro is not None and not futuro.done():
            futuro.set_result(mensagem)


async def chamar_ferramenta(id_usuario: str, nome: str, argumentos: dict, timeout: float = 25.0) -> dict:
    websocket = _conexoes.get(id_usuario)
    if websocket is None:
        raise RuntimeError("O PC não está conectado agora.")

    id_requisicao = str(uuid.uuid4())
    futuro: asyncio.Future = asyncio.get_event_loop().create_future()
    _pendentes[id_requisicao] = futuro
    await websocket.send_text(json.dumps({"id_requisicao": id_requisicao, "ferramenta": nome, "argumentos": argumentos}))
    try:
        return await asyncio.wait_for(futuro, timeout=timeout)
    finally:
        _pendentes.pop(id_requisicao, None)
