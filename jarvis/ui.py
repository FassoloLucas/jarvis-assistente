"""HUD holográfico do J.A.R.V.I.S., renderizado como página local via pywebview.

Troca o antigo Canvas do Tkinter (formas geométricas simples) por uma janela
nativa que carrega `jarvis/assets/hud.html` — um HUD com anel de radar,
partículas, núcleo pulsante e waveform, tudo reagindo ao estado atual. O
Python empurra mudanças de estado pro HTML via `window.evaluate_js`; a
própria página roda um ciclo de demonstração sozinha até receber o primeiro
estado real do cérebro, então também serve como prévia isolada (dá pra abrir
o HTML puro no navegador pra iterar no visual sem precisar da automação
inteira rodando).
"""

import json
import threading
from pathlib import Path

import webview

HTML_PATH = Path(__file__).parent / "assets" / "hud.html"


class JarvisUI:
    def __init__(self):
        self.estado_atual = "iniciando"
        self._window = webview.create_window(
            title="J.A.R.V.I.S. | Core HUD - Demonstração",
            url=HTML_PATH.resolve().as_uri(),
            width=520,
            height=820,
            resizable=False,
            background_color="#05090c",
        )

    def aguardar_pronto(self, timeout=10):
        """Bloqueia até a página do HUD terminar de carregar, pra garantir
        que `window.jarvisSetState` já existe antes do primeiro `mudar_estado`."""
        self._window.events.loaded.wait(timeout)

    def mudar_estado(self, estado, texto, cor=None):
        """Mesma assinatura (estado, texto, cor) que o brain.py já usava com
        o Tkinter, pra não precisar mexer na orquestração. `cor` não é mais
        necessário — o HTML já sabe a cor de cada estado — mas fica aceito
        e ignorado por compatibilidade."""
        self.estado_atual = estado
        payload = json.dumps({"estado": estado, "texto": texto})
        try:
            self._window.evaluate_js(f"window.jarvisSetState({payload})")
        except Exception as e:
            print(f"Erro ao atualizar o HUD: {e}")

    def after(self, ms, func, *args):
        """Compat com o padrão `app.after(...)` que o brain.py usa pra
        despachar chamadas com segurança a partir da thread do cérebro."""
        if ms <= 0:
            func(*args)
        else:
            threading.Timer(ms / 1000, func, args=args).start()

    def destroy(self):
        self._window.destroy()

    def start(self, func_inicial=None):
        """Sobe o loop de eventos da janela (bloqueante) — equivalente ao
        antigo `app.mainloop()`. `func_inicial`, se passado, roda numa
        thread separada assim que a janela existir; é ali que entra o
        cérebro do J.A.R.V.I.S. (veja `main.py`)."""
        webview.start(func_inicial, gui="edgechromium", debug=False)
