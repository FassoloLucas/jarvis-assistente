"""Integração com o Google Calendar de verdade (não uma agenda local
reimplementada) — o J.A.R.V.I.S. enxerga e cria compromissos na sua conta
Google de verdade.

Usa OAuth (`InstalledAppFlow`): na primeira vez que qualquer função daqui
for chamada sem um token salvo, abre o navegador padrão pra você logar na
sua conta Google e autorizar o acesso. Depois disso, o token fica salvo
localmente (`jarvis/data/google_token.json`) e se renova sozinho — não
pede login de novo, a menos que você revogue o acesso manualmente.

Setup necessário uma única vez (veja o README pro passo a passo completo):
1. Criar um projeto no Google Cloud Console e ativar a "Google Calendar API".
2. Criar uma credencial OAuth do tipo "App para computador" (Desktop app).
3. Baixar o JSON da credencial e salvar em `jarvis/data/google_credentials.json`.
4. Rodar `python setup_google_calendar.py` uma vez pra autorizar (ou deixar
   a primeira chamada real do J.A.R.V.I.S. disparar o fluxo).

Escopo pedido: só `calendar.events` (ler/criar/editar eventos) — não pede
acesso pra apagar ou reconfigurar o calendário inteiro.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

# As libs do Google (google-auth, google-auth-oauthlib, google-api-python-client)
# são importadas dentro das funções que as usam, não aqui no topo — só o
# `googleapiclient.discovery` sozinho leva uns 7s pra importar, e isso
# rodava sempre no boot do J.A.R.V.I.S., mesmo em sessões que nunca usam a
# agenda. `from __future__ import annotations` deixa o `-> Credentials` em
# `_autenticar` funcionar sem precisar do import lá em cima.

ESCOPOS = ["https://www.googleapis.com/auth/calendar.events"]

CAMINHO_CREDENCIAIS = Path(__file__).parent / "data" / "google_credentials.json"
CAMINHO_TOKEN = Path(__file__).parent / "data" / "google_token.json"

CALENDARIO_ID = "primary"  # calendário principal da conta autenticada
FUSO_HORARIO = "America/Sao_Paulo"


def _autenticar() -> Credentials:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CAMINHO_CREDENCIAIS.exists():
        raise RuntimeError(
            "Credenciais do Google Calendar não encontradas. Baixe o JSON OAuth do Google "
            f"Cloud Console e salve em {CAMINHO_CREDENCIAIS} (veja o README)."
        )

    credenciais = None
    if CAMINHO_TOKEN.exists():
        credenciais = Credentials.from_authorized_user_file(str(CAMINHO_TOKEN), ESCOPOS)

    if not credenciais or not credenciais.valid:
        if credenciais and credenciais.expired and credenciais.refresh_token:
            credenciais.refresh(Request())
        else:
            fluxo = InstalledAppFlow.from_client_secrets_file(str(CAMINHO_CREDENCIAIS), ESCOPOS)
            credenciais = fluxo.run_local_server(port=0)
        CAMINHO_TOKEN.parent.mkdir(parents=True, exist_ok=True)
        CAMINHO_TOKEN.write_text(credenciais.to_json())

    return credenciais


def _servico():
    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=_autenticar())


def listar_proximos_eventos(dias_a_frente: int = 7, max_resultados: int = 10) -> list[dict]:
    servico = _servico()
    agora = datetime.utcnow()
    limite = agora + timedelta(days=dias_a_frente)
    resposta = (
        servico.events()
        .list(
            calendarId=CALENDARIO_ID,
            timeMin=agora.isoformat() + "Z",
            timeMax=limite.isoformat() + "Z",
            maxResults=max_resultados,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    eventos = []
    for item in resposta.get("items", []):
        inicio = item["start"].get("dateTime", item["start"].get("date"))
        eventos.append(
            {
                "id": item["id"],
                "titulo": item.get("summary", "(sem título)"),
                "inicio": inicio,
                "local": item.get("location"),
            }
        )
    return eventos


def criar_evento(
    titulo: str,
    inicio_iso: str,
    fim_iso: str | None = None,
    descricao: str | None = None,
    local: str | None = None,
) -> dict:
    servico = _servico()
    if not fim_iso:
        inicio_dt = datetime.fromisoformat(inicio_iso)
        fim_iso = (inicio_dt + timedelta(hours=1)).isoformat()

    corpo = {
        "summary": titulo,
        "start": {"dateTime": inicio_iso, "timeZone": FUSO_HORARIO},
        "end": {"dateTime": fim_iso, "timeZone": FUSO_HORARIO},
    }
    if descricao:
        corpo["description"] = descricao
    if local:
        corpo["location"] = local

    evento_criado = servico.events().insert(calendarId=CALENDARIO_ID, body=corpo).execute()
    return {"id": evento_criado["id"], "link": evento_criado.get("htmlLink")}
