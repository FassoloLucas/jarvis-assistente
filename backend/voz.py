"""Geração de áudio (texto→fala) pro app de celular — mesma voz do desktop
(`config.VOZ_TTS`, edge-tts), gerada aqui no backend porque o app não deve
ter uma chave/lib de TTS própria embutida, e assim os dois ficam com a
"mesma persona sonora".

Diferente de `jarvis/audio.py` (que quebra a fala em frases pra começar a
tocar mais cedo, streamando por pedaços), aqui devolve o áudio da resposta
inteira de uma vez — o app faz uma chamada HTTP só, mais simples do lado do
cliente. Streaming por frases pro app é uma otimização futura, se a demora
incomodar na prática (mesmo motivo documentado no README, seção "Fala
(TTS)").
"""

import edge_tts

from jarvis import config


async def gerar_audio_mp3(texto: str) -> bytes:
    texto_limpo = texto.replace("*", "").replace('"', "").replace("#", "")
    comunicador = edge_tts.Communicate(texto_limpo, config.VOZ_TTS, rate=config.TAXA_FALA)
    pedacos = bytearray()
    async for chunk in comunicador.stream():
        if chunk["type"] == "audio":
            pedacos += chunk["data"]
    return bytes(pedacos)
