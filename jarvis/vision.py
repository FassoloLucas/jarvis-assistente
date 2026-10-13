"""Captura de tela para a ferramenta `ver_tela`."""

import base64
import io


def tirar_print_base64() -> str:
    # Import tardio: pyautogui precisa de um display de verdade (X11/etc),
    # e este módulo agora também é importado pelo backend (Render, Linux
    # headless) através de jarvis.tools — sem isso, o import quebrava lá
    # mesmo sem essa função nunca ser chamada.
    import pyautogui

    screenshot = pyautogui.screenshot().convert("RGB")
    screenshot.thumbnail((1280, 1280))
    buffer = io.BytesIO()
    screenshot.save(buffer, format="JPEG", quality=80)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")
