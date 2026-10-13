"""Ponto de entrada legado — mantém `python javis.py` funcionando.

A implementação foi modularizada e agora vive no pacote `jarvis/`
(config, persona, web, vision, audio, tools, ui, brain, main). Veja o
README.md para uma visão geral da nova estrutura.
"""

from jarvis.main import iniciar

if __name__ == "__main__":
    iniciar()
