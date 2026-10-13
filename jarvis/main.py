"""Ponto de entrada do J.A.R.V.I.S.: monta o HUD e inicia a thread do cérebro."""

from . import relay
from .brain import Cerebro
from .ui import JarvisUI


def iniciar():
    ui = JarvisUI()
    cerebro = Cerebro(ui)

    # Sem efeito se jarvis/data/relay_credentials.json não existir — ver
    # relay.py. Fica numa thread própria, independente do resto do boot.
    relay.iniciar()

    def _iniciar_cerebro():
        # Só começa a falar/ouvir depois que o HUD terminou de carregar,
        # senão `window.jarvisSetState` ainda não existiria na página.
        ui.aguardar_pronto()
        cerebro.loop()

    ui.start(_iniciar_cerebro)  # bloqueante: sobe o loop de eventos da janela


if __name__ == "__main__":
    iniciar()
