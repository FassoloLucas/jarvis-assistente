"""Backend HTTP do J.A.R.V.I.S. mobile.

Rodar localmente (a partir da raiz do projeto, pra `jarvis`/`backend`
resolverem como pacotes-irmãos):

    .venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload

Ver README ("App de celular") pra instruções de hospedagem.
"""

from dotenv import load_dotenv

# Precisa rodar antes de qualquer outro import deste pacote: `auth.py` lê
# JARVIS_JWT_SECRET do ambiente assim que é importado (não tardio) — sem
# isso aqui em cima, a ordem de import podia carregar `auth` antes do
# `.env` existir (só carregado de verdade quando `jarvis.config` era
# importado, mais abaixo na cadeia).
load_dotenv()

from pathlib import Path  # noqa: E402

from fastapi import Depends, FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from . import agentes, auth, nucleo, versao, voz  # noqa: E402

app = FastAPI(title="J.A.R.V.I.S. Backend")

CAMINHO_APK = Path(__file__).parent / "static" / "app-release.apk"


class CadastroRequest(BaseModel):
    email: str
    senha: str
    nome: str


class LoginRequest(BaseModel):
    email: str
    senha: str


class ChatRequest(BaseModel):
    mensagem: str
    conversa_id: str | None = None


class FalarRequest(BaseModel):
    texto: str


def _usuario_atual(authorization: str = Header(default="")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Token ausente. Faça login em /login e mande o token em 'Authorization: Bearer <token>'.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        return auth.verificar_token(token)
    except Exception:
        raise HTTPException(401, "Token inválido ou expirado. Faça login de novo.")


@app.get("/")
def raiz():
    return {"status": "ok", "servico": "J.A.R.V.I.S. Backend"}


@app.get("/versao")
def versao_atual():
    """Sem autenticação de propósito — o app confere isso antes até de
    mostrar a tela de login, pra pegar uma versão quebrada de login também."""
    return {"versao_minima": versao.VERSAO_MINIMA, "apk_url": "/apk/latest"}


@app.get("/apk/latest")
def apk_mais_recente():
    if not CAMINHO_APK.exists():
        raise HTTPException(404, "Nenhum APK publicado ainda.")
    return FileResponse(CAMINHO_APK, media_type="application/vnd.android.package-archive", filename="jarvis.apk")


@app.post("/cadastro")
def cadastro(dados: CadastroRequest):
    try:
        usuario = auth.registrar(dados.email, dados.senha, dados.nome)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True, "usuario": usuario}


@app.post("/login")
def login(dados: LoginRequest):
    usuario = auth.autenticar(dados.email, dados.senha)
    if not usuario:
        raise HTTPException(401, "E-mail ou senha incorretos.")
    return {"token": auth.gerar_token(usuario)}


@app.get("/conversas")
def listar_conversas(usuario: dict = Depends(_usuario_atual)):
    return {"conversas": nucleo.listar_conversas(usuario["sub"])}


@app.post("/conversas")
def nova_conversa(usuario: dict = Depends(_usuario_atual)):
    interlocutor = {"nome": usuario.get("nome"), "email": usuario.get("email")}
    return {"id": nucleo.criar_conversa(usuario["sub"], interlocutor)}


@app.get("/conversas/{conversa_id}")
def obter_conversa(conversa_id: str, usuario: dict = Depends(_usuario_atual)):
    try:
        mensagens = nucleo.carregar_conversa(usuario["sub"], conversa_id)
    except ValueError as e:
        raise HTTPException(404, str(e))
    # Só o que faz sentido mostrar numa tela de chat — sem system prompt
    # nem as mensagens intermediárias de tool-calling.
    exibiveis = [
        {"role": m["role"], "content": m["content"]}
        for m in mensagens
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    return {"mensagens": exibiveis}


@app.delete("/conversas/{conversa_id}")
def apagar_conversa(conversa_id: str, usuario: dict = Depends(_usuario_atual)):
    """Apaga só o histórico dessa conversa — a memória de longo prazo
    (fatos aprendidos) fica intacta, é um banco separado (ver
    jarvis/memoria.py / backend/nucleo.py)."""
    apagou = nucleo.apagar_conversa(usuario["sub"], conversa_id)
    if not apagou:
        raise HTTPException(404, "Conversa não encontrada.")
    return {"ok": True}


@app.post("/chat")
async def chat(dados: ChatRequest, usuario: dict = Depends(_usuario_atual)):
    id_usuario = usuario["sub"]
    interlocutor = {"nome": usuario.get("nome"), "email": usuario.get("email")}
    id_conversa = dados.conversa_id or nucleo.criar_conversa(id_usuario, interlocutor)
    try:
        historico = nucleo.carregar_conversa(id_usuario, id_conversa, interlocutor)
    except ValueError as e:
        raise HTTPException(404, str(e))

    # Título só é definido na primeira mensagem de verdade (histórico com
    # só o system prompt, nada mais ainda).
    primeira_mensagem = dados.mensagem if len(historico) == 1 else None

    resultado = await nucleo.executar_turno(historico, dados.mensagem, id_usuario)
    nucleo.salvar_conversa(id_usuario, id_conversa, resultado["mensagens"], primeira_mensagem)
    return {"resposta": resultado["resposta"], "conversa_id": id_conversa}


@app.post("/falar")
async def falar(dados: FalarRequest, usuario: dict = Depends(_usuario_atual)):
    """Gera o áudio (mp3) de um texto com a mesma voz do desktop — o app
    chama isso logo depois de receber a resposta de `/chat` pra tocar em
    voz alta."""
    audio_mp3 = await voz.gerar_audio_mp3(dados.texto)
    return Response(content=audio_mp3, media_type="audio/mpeg")


@app.websocket("/pc/conectar")
async def pc_conectar(websocket: WebSocket, token: str):
    """O `Cerebro` desktop (jarvis/relay.py) conecta aqui, de saída, usando
    o mesmo login da conta do app — contorna o NAT de casa (o PC nunca
    precisa ser alcançável de fora, só ele abrir essa conexão). Enquanto
    aberta, essa conexão é o canal usado por `agentes.chamar_ferramenta`
    pra relayar comandos de automação vindos do celular."""
    try:
        usuario = auth.verificar_token(token)
    except Exception:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    id_usuario = usuario["sub"]
    agentes.registrar(id_usuario, websocket)
    try:
        await agentes.escutar_respostas(websocket)
    except WebSocketDisconnect:
        pass
    finally:
        agentes.desregistrar(id_usuario)
