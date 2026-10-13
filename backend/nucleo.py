"""Núcleo de conversa do backend — o mesmo tipo de loop de tool-calling que
`jarvis/brain.py` usa no desktop (`Cerebro.processar_comando` /
`_executar_tool_calls`), mas sem nenhuma dependência de UI/voz (pygame,
pyautogui, wake-word) e capaz de atender várias pessoas ao mesmo tempo (o
desktop assume um `self.historico` único; aqui o histórico é carregado e
salvo por usuário, a cada requisição).

Decisão consciente: em vez de refatorar `jarvis/brain.py` — que já está em
uso diário de verdade — pra extrair esse loop dali, este módulo escreve uma
versão própria, específica pro backend. Isso custa um loop de tool-calling
escrito duas vezes (aqui e em `Cerebro`), mas evita qualquer risco de
regressão no app desktop já em uso. As duas versões chamam exatamente os
mesmos `tools.TOOL_HANDLERS` por baixo, então o comportamento de cada
ferramenta em si nunca diverge — só a orquestração do loop é duplicada.

As ferramentas em `tools.FERRAMENTAS_NUVEM` rodam direto aqui no backend
(mesmos `tools.TOOL_HANDLERS` do desktop). As demais (automação do PC:
abrir_programa, ver_tela, etc.) só ficam disponíveis pro modelo quando
`agentes.conectado(id_usuario)` — aí a chamada é relayada pro PC via
WebSocket (`agentes.chamar_ferramenta`) em vez de executada aqui (o backend
em si não tem tela/teclado pra automatizar). Sem PC conectado, o modelo só
vê o catálogo de nuvem, então nem tenta chamar automação — não precisa de
tratamento de erro especial pra esse caso.
"""

import json
from datetime import datetime, timezone

from openai import OpenAI

from jarvis import config, persona, tools

from . import agentes

_cliente_ia = OpenAI(api_key=config.OPENROUTER_API_KEY, base_url=config.OPENROUTER_BASE_URL)

_FERRAMENTAS_NUVEM = [t for t in tools.TOOLS if t["function"]["name"] in tools.FERRAMENTAS_NUVEM]

_cliente_mongo = None


def _conversas():
    """Coleção Mongo que guarda o histórico de mensagens por usuário —
    import tardio do pymongo pelo mesmo motivo de `jarvis/memoria.py` (essa
    instalação específica pode não ter a lib)."""
    global _cliente_mongo
    if _cliente_mongo is None:
        import certifi
        from pymongo import MongoClient

        _cliente_mongo = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=8000, tlsCAFile=certifi.where())
    return _cliente_mongo[config.MONGODB_DB]["conversas"]


def _system_prompt_atual(interlocutor: dict | None = None) -> dict:
    # Sempre recém-montado, nunca o que foi salvo da última vez — a memória
    # é compartilhada entre superfícies (o chefe pode ter ensinado algo novo
    # pelo desktop entre uma mensagem do app e outra); sem isso, a conversa
    # ficava presa na "foto" da memória de quando ela começou. `interlocutor`
    # (nome/e-mail de quem está logado, vindo do token JWT) avisa o modelo
    # com quem ele está falando agora — mais de uma pessoa usa essa
    # plataforma, com memória compartilhada entre elas, mas cada uma é um
    # interlocutor diferente na conversa.
    return {"role": "system", "content": persona.montar_system_prompt(interlocutor)}


def criar_conversa(id_usuario: str, interlocutor: dict | None = None) -> str:
    agora = datetime.now(timezone.utc)
    documento = {
        "id_usuario": id_usuario,
        "titulo": None,
        "mensagens": [_system_prompt_atual(interlocutor)],
        "criado_em": agora,
        "atualizado_em": agora,
    }
    resultado = _conversas().insert_one(documento)
    return str(resultado.inserted_id)


def carregar_conversa(id_usuario: str, id_conversa: str, interlocutor: dict | None = None) -> list[dict]:
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        documento = _conversas().find_one({"_id": ObjectId(id_conversa), "id_usuario": id_usuario})
    except InvalidId:
        documento = None
    if not documento:
        raise ValueError("Conversa não encontrada (pode ter sido apagada, ou é de outra conta).")

    mensagens = documento["mensagens"]
    mensagens[0] = _system_prompt_atual(interlocutor)
    return mensagens


def salvar_conversa(id_usuario: str, id_conversa: str, mensagens: list[dict], primeira_mensagem: str | None) -> None:
    from bson import ObjectId

    atualizacao = {"mensagens": mensagens, "atualizado_em": datetime.now(timezone.utc)}
    if primeira_mensagem:
        # Só define o título na primeira mensagem de verdade da conversa —
        # chamadas seguintes passam primeira_mensagem=None e não mexem nisso.
        atualizacao["titulo"] = primeira_mensagem[:60]
    _conversas().update_one(
        {"_id": ObjectId(id_conversa), "id_usuario": id_usuario},
        {"$set": atualizacao},
    )


def apagar_conversa(id_usuario: str, id_conversa: str) -> bool:
    """Apaga só o histórico da conversa (coleção `conversas`) — nunca toca
    na memória de longo prazo (coleção `memorias`, ver jarvis/memoria.py),
    que é um banco completamente separado. Apagar uma conversa não faz o
    Jarvis "esquecer" nada que ele aprendeu."""
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        resultado = _conversas().delete_one({"_id": ObjectId(id_conversa), "id_usuario": id_usuario})
    except InvalidId:
        return False
    return resultado.deleted_count > 0


def listar_conversas(id_usuario: str) -> list[dict]:
    documentos = (
        _conversas()
        .find({"id_usuario": id_usuario}, {"mensagens": 0})
        .sort("atualizado_em", -1)
    )
    return [
        {
            "id": str(d["_id"]),
            "titulo": d.get("titulo") or "Nova conversa",
            "atualizado_em": d["atualizado_em"].isoformat() if d.get("atualizado_em") else None,
        }
        for d in documentos
    ]


async def _executar_ferramentas(mensagem_ia, mensagens: list[dict], id_usuario: str) -> None:
    # Convertido pra dict puro (em vez de anexar o objeto ChatCompletionMessage
    # do SDK direto) — esse histórico é salvo no MongoDB pra continuidade
    # entre chamadas, e o objeto do SDK não é serializável em BSON. O
    # `brain.py` desktop nunca bate nisso porque não persiste esse histórico
    # intermediário de tool-calling, só o resultado final.
    mensagens.append(
        {
            "role": "assistant",
            "content": mensagem_ia.content,
            "tool_calls": [
                {
                    "id": chamada.id,
                    "type": "function",
                    "function": {"name": chamada.function.name, "arguments": chamada.function.arguments},
                }
                for chamada in mensagem_ia.tool_calls
            ],
        }
    )
    for chamada in mensagem_ia.tool_calls:
        nome = chamada.function.name
        try:
            argumentos = json.loads(chamada.function.arguments or "{}")
        except json.JSONDecodeError:
            argumentos = {}

        if nome in tools.FERRAMENTAS_NUVEM:
            try:
                saida = tools.TOOL_HANDLERS[nome](argumentos)
                resultado = saida.get("resultado", "ok")
            except Exception as e:
                # Log de verdade (aparece no log do Render) além da frase
                # curta que vai pro modelo — sem isso, o erro real só existe
                # dentro do contexto da conversa, invisível pra debugar.
                print(f"Erro executando ferramenta '{nome}' com args {argumentos}: {e!r}")
                resultado = f"Falha ao executar {nome}: {e}"
        elif agentes.conectado(id_usuario):
            try:
                resposta_pc = await agentes.chamar_ferramenta(id_usuario, nome, argumentos)
                resultado = resposta_pc.get("resultado", "ok")
            except Exception as e:
                print(f"Erro relayando ferramenta '{nome}' pro PC com args {argumentos}: {e!r}")
                resultado = f"Falha ao executar {nome} no PC: {e}"
        else:
            # Não deveria acontecer (o modelo só vê essa ferramenta na
            # lista quando o PC está conectado — ver _ferramentas_para) mas
            # não custa ter uma resposta segura caso o PC caia bem no meio.
            resultado = f"Ferramenta '{nome}' precisa do PC conectado, e ele caiu."

        mensagens.append({"role": "tool", "tool_call_id": chamada.id, "content": resultado})


def _ferramentas_para(id_usuario: str) -> list[dict]:
    return tools.TOOLS if agentes.conectado(id_usuario) else _FERRAMENTAS_NUVEM


async def executar_turno(mensagens: list[dict], comando_usuario: str, id_usuario: str) -> dict:
    """Processa um comando dentro de um histórico de conversa (mensagens no
    formato da API OpenAI) e devolve o histórico atualizado junto com a
    resposta final em texto. Se o PC do usuário estiver conectado (ver
    `agentes.py`), o modelo também enxerga as ferramentas de automação —
    sem isso, só as de nuvem."""
    mensagens_originais = mensagens
    mensagem_usuario = {"role": "user", "content": comando_usuario}
    mensagens = mensagens + [mensagem_usuario]

    for _ in range(config.MAX_RODADAS_TOOL_CALLING):
        resposta = _cliente_ia.chat.completions.create(
            model=config.MODEL_ID,
            messages=mensagens,
            tools=_ferramentas_para(id_usuario),
            temperature=config.TEMPERATURE,
        )
        mensagem_ia = resposta.choices[0].message

        if mensagem_ia.tool_calls:
            await _executar_ferramentas(mensagem_ia, mensagens, id_usuario)
            continue

        texto = mensagem_ia.content or ""
        mensagens.append({"role": "assistant", "content": texto})
        return {"mensagens": mensagens, "resposta": texto}

    # Estourou o limite de rodadas sem chegar numa resposta final — em vez
    # de salvar o histórico inteiro com todas as tentativas de ferramenta
    # que não deram em nada, descarta essa sequência fracassada e guarda só
    # a pergunta + a desculpa. Sem isso, uma conversa que já tropeçou nisso
    # uma vez ficava com esse "lixo" preso no contexto — e visto na prática:
    # deixava as próximas mensagens da mesma conversa mais propensas a cair
    # no mesmo loop de novo, além de inflar a conversa à toa.
    texto_erro = "Me perdi numa sequência de ações. Pode repetir o pedido?"
    mensagens_limpas = mensagens_originais + [mensagem_usuario, {"role": "assistant", "content": texto_erro}]
    return {"mensagens": mensagens_limpas, "resposta": texto_erro}
