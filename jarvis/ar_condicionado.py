"""Controle do ar condicionado via ConnectLife (Hisense, Gorenje, ASKO,
ATAG, ETNA Connect) — API não-oficial (engenharia reversa, biblioteca
`connectlife` de github.com/oyvindwe/connectlife). Ver README ("Ar
condicionado") e `setup_connectlife.py` pro cadastro da conta/aparelho.

O mapeamento de propriedades abaixo (MODOS, VELOCIDADES, faixa de
temperatura) foi descoberto via `ConnectLifeApi.get_property_list()` —
consulta direta à própria API pro par device_type_code/device_feature_code
do aparelho do chefe (um ar condicionado de janela: tipo "008", feature
"301"). Isso é específico desse modelo: outro aparelho pode ter uma faixa de
valores diferente (ex: mais níveis de velocidade, ou incluir modo "aquecer").
Se um dia trocar de aparelho, rode `setup_connectlife.py` de novo e consulte
`get_property_list` pra atualizar esses valores.

Recurso opcional e "à prova de travar sozinho": se ninguém rodou o cadastro
ainda (arquivo de credenciais não existe), `configurado()` devolve False —
quem chama deve tratar isso como "recurso desligado", nunca travar o
assistente por causa disso. Pelo mesmo motivo, a lib `connectlife` (e suas
dependências, aiohttp/cryptography) só é importada dentro das funções que
precisam dela, nunca aqui no topo — assim o resto do J.A.R.V.I.S. continua
rodando normalmente em ambientes sem essas libs instaladas (ex: o Python
global da máquina, fora da venv do projeto), contanto que ninguém tenha
cadastrado a conta ainda.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from connectlife.api import ConnectLifeApi

CAMINHO_CREDENCIAIS = Path(__file__).parent / "data" / "connectlife_credentials.json"


def _executar(coroutine):
    """Roda uma coroutine e devolve o resultado, funcionando tanto chamado
    de um contexto síncrono comum (desktop: `tools.py` roda numa thread sem
    loop assíncrono nenhum — `_executar()` de boa) quanto de dentro de um
    loop assíncrono já em execução (backend do app: o endpoint `/chat` é
    `async def`, e `_executar()` não pode ser chamado com um loop já
    rodando na mesma thread — estourava `RuntimeError`, e a ferramenta
    "falhava" silenciosamente pro modelo). Nesse segundo caso, roda a
    coroutine numa thread própria com seu próprio loop, isolada da do
    chamador, e espera o resultado."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coroutine)

    resultado: dict = {}

    def _rodar_em_thread_propria():
        try:
            resultado["valor"] = asyncio.run(coroutine)
        except Exception as e:
            resultado["erro"] = e

    thread = threading.Thread(target=_rodar_em_thread_propria)
    thread.start()
    thread.join()
    if "erro" in resultado:
        raise resultado["erro"]
    return resultado.get("valor")

# t_work_mode: só estes 4 valores são aceitos nesse modelo (descoberto via
# get_property_list) — sem "aquecer", ar de janela só resfria. A numeração
# segue a convenção usual da Midea (fabricante por trás da Hisense) pros
# valores que esse aparelho de fato aceita.
MODOS = {"auto": "0", "frio": "2", "seco": "3", "ventilar": "5"}
_MODOS_REVERSO = {v: k for k, v in MODOS.items()}

# t_fan_speed: só 3 níveis nesse modelo (sem "automático").
VELOCIDADES = {"baixa": "2", "media": "3", "alta": "4"}
_VELOCIDADES_REVERSO = {v: k for k, v in VELOCIDADES.items()}

TEMP_MIN, TEMP_MAX = 16, 30  # graus Celsius (t_temp_type fixado em "0")

_api: "Optional[ConnectLifeApi]" = None
_puid: Optional[str] = None


# No backend hospedado (Render), não existe jarvis/data/connectlife_credentials.json
# — esse arquivo tem a senha real da conta ConnectLife dentro, então nunca
# foi (nem deveria ser) commitado no git. Lá, as mesmas credenciais vêm de
# variáveis de ambiente em vez do arquivo local. O desktop continua usando
# o arquivo normalmente (nunca precisou mudar nada por lá). Só email/senha/
# puid são de fato usados em runtime (device_type_code/feature_code só
# importaram na descoberta inicial das propriedades, ver módulo docstring).
_VARS_AMBIENTE = ("CONNECTLIFE_EMAIL", "CONNECTLIFE_SENHA", "CONNECTLIFE_PUID")


def configurado() -> bool:
    return CAMINHO_CREDENCIAIS.exists() or all(os.environ.get(v) for v in _VARS_AMBIENTE)


def _carregar_credenciais() -> dict:
    if CAMINHO_CREDENCIAIS.exists():
        return json.loads(CAMINHO_CREDENCIAIS.read_text(encoding="utf-8"))
    return {
        "email": os.environ["CONNECTLIFE_EMAIL"],
        "senha": os.environ["CONNECTLIFE_SENHA"],
        "puid": os.environ["CONNECTLIFE_PUID"],
    }


async def _cliente() -> "tuple[ConnectLifeApi, str]":
    """Reusa a mesma sessão autenticada entre chamadas — a lib já renova o
    token sozinha quando expira. Logar do zero toda vez seria bem mais lento
    (login completo = 4 idas e vindas de rede: Gigya login, JWT, authorize,
    troca de código por token) e desnecessário enquanto o processo do
    J.A.R.V.I.S. continua rodando."""
    global _api, _puid
    if _api is None:
        from connectlife.api import ConnectLifeApi

        dados = _carregar_credenciais()
        _api = ConnectLifeApi(dados["email"], dados["senha"])
        _puid = dados["puid"]
        await _api.login()
    return _api, _puid


async def _ler_estado_async() -> dict:
    api, puid = await _cliente()
    for aparelho in await api.get_appliances():
        if aparelho.puid == puid:
            return aparelho.status_list
    raise RuntimeError("Ar condicionado não encontrado na conta ConnectLife (foi removido/desvinculado?).")


async def _aplicar_async(propriedades: dict[str, str]) -> None:
    api, puid = await _cliente()
    await api.update_appliance(puid, propriedades)


def ligar(ligado: bool = True) -> str:
    _executar(_aplicar_async({"t_power": "1" if ligado else "0"}))
    return "ligado" if ligado else "desligado"


def definir_temperatura(graus: int) -> int:
    graus = max(TEMP_MIN, min(TEMP_MAX, int(graus)))
    # t_temp_type junto pra garantir que "graus" seja sempre lido como
    # Celsius, independente de qual unidade estava configurada antes.
    _executar(_aplicar_async({"t_temp": str(graus), "t_temp_type": "0"}))
    return graus


def definir_modo(modo: str) -> str:
    codigo = MODOS.get(modo)
    if codigo is None:
        raise ValueError(f"Modo {modo!r} desconhecido. Use um de: {', '.join(MODOS)}.")
    _executar(_aplicar_async({"t_work_mode": codigo}))
    return modo


def definir_velocidade(velocidade: str) -> str:
    codigo = VELOCIDADES.get(velocidade)
    if codigo is None:
        raise ValueError(f"Velocidade {velocidade!r} desconhecida. Use uma de: {', '.join(VELOCIDADES)}.")
    _executar(_aplicar_async({"t_fan_speed": codigo}))
    return velocidade


def status() -> dict:
    """Lê o estado atual do aparelho. Atenção: logo depois de um comando,
    isso pode devolver o estado ANTERIOR por alguns segundos — o aparelho
    físico leva um tempo pra reportar a mudança de volta pra nuvem
    ConnectLife (visto na prática: comandos aceitos na hora, releitura só
    atualizada ~10s depois)."""
    estado = _executar(_ler_estado_async())
    return {
        "ligado": str(estado.get("t_power")) == "1",
        "temperatura": estado.get("t_temp"),
        "temperatura_ambiente": estado.get("f_temp_in"),
        "modo": _MODOS_REVERSO.get(str(estado.get("t_work_mode")), "desconhecido"),
        "velocidade": _VELOCIDADES_REVERSO.get(str(estado.get("t_fan_speed")), "desconhecido"),
    }
