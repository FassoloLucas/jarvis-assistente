"""Biometria de voz: reconhece SE quem está falando é o chefe — diferente
do resto do reconhecimento de voz do projeto (`audio.py`/`wakeword.py`),
que transcreve O QUE foi dito, não QUEM disse.

Usa o Resemblyzer (rede neural pré-treinada, roda 100% local depois de
instalada — sem conta nem chave de API) pra transformar um trecho de áudio
num "d-vector": uma impressão numérica da voz de quem falou. O cadastro
(`cadastrar_perfil`, ver `setup_perfil_vocal.py`) salva o d-vector do chefe;
depois, cada comando é comparado a esse perfil por similaridade de cosseno.

Recurso opcional e "à prova de travar sozinho": se ninguém rodou o cadastro
ainda (arquivo em `CAMINHO_PERFIL` não existe) ou algo dá errado ao
processar o áudio, `verificar()` devolve `None` — quem chama deve tratar
isso como "deixa passar", nunca como recusa. Só devolve `False` quando
conseguiu comparar de verdade e a voz não bateu.

Dependências pesadas (`torch`, `resemblyzer`, `soundfile`) só são importadas
dentro das funções que precisam delas (nunca no topo do módulo) — assim o
resto do J.A.R.V.I.S. continua rodando normalmente em ambientes sem essas
libs instaladas, contanto que ninguém tenha cadastrado um perfil ainda. Veja
o README ("Biometria de voz") pra instruções de instalação.
"""

from pathlib import Path
from typing import Optional

import numpy as np

from . import config

CAMINHO_PERFIL = Path(__file__).parent / "data" / "perfil_vocal.npy"

_encoder = None  # carregado sob demanda na primeira verificação/cadastro


def perfil_cadastrado() -> bool:
    return CAMINHO_PERFIL.exists()


def _carregar_encoder():
    global _encoder
    if _encoder is None:
        from resemblyzer import VoiceEncoder

        _encoder = VoiceEncoder()
    return _encoder


def _wav_bytes_para_embedding(wav_bytes: bytes) -> np.ndarray:
    import io

    import soundfile as sf
    from resemblyzer import preprocess_wav

    dados, taxa_amostragem = sf.read(io.BytesIO(wav_bytes))
    wav_preprocessado = preprocess_wav(dados, source_sr=taxa_amostragem)
    return _carregar_encoder().embed_utterance(wav_preprocessado)


def cadastrar_perfil(wav_bytes: bytes) -> None:
    """Salva a "impressão vocal" do chefe a partir de uma gravação de
    cadastro (ver `setup_perfil_vocal.py`). Sobrescreve um perfil anterior,
    se houver."""
    embedding = _wav_bytes_para_embedding(wav_bytes)
    CAMINHO_PERFIL.parent.mkdir(parents=True, exist_ok=True)
    np.save(CAMINHO_PERFIL, embedding)


def verificar(wav_bytes: bytes) -> Optional[bool]:
    """Compara o áudio de um comando com o perfil vocal cadastrado.

    Devolve True (bateu com o chefe), False (voz diferente) ou None quando
    não dá pra decidir (sem perfil cadastrado, ou erro ao processar o
    áudio) — nesse último caso o chamador deve deixar passar, pra essa
    camada extra nunca travar o assistente sozinha."""
    if not perfil_cadastrado():
        return None
    try:
        perfil = np.load(CAMINHO_PERFIL)
        embedding = _wav_bytes_para_embedding(wav_bytes)
        similaridade = float(
            np.dot(perfil, embedding) / (np.linalg.norm(perfil) * np.linalg.norm(embedding))
        )
        return similaridade >= config.LIMIAR_SIMILARIDADE_VOZ
    except Exception as e:
        print(f"Erro na verificação de voz: {e}")
        return None
