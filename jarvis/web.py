"""Busca de informação em tempo real (clima, notícias, busca geral).

Lógica praticamente idêntica à original — o que muda é *quem* decide
chamar isso: antes era uma lista fixa de palavras-chave verificada em todo
comando (`gatilhos_pesquisa`); agora é o próprio modelo, através da
ferramenta `buscar_web` (veja `tools.py`), que decide quando precisa desses
dados. Isso elimina falsos positivos/negativos de correspondência de texto.
"""

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from . import config


def _buscar_noticias() -> str | None:
    req = urllib.request.Request(config.FEED_NOTICIAS, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as resposta:
        xml_data = resposta.read()
        root = ET.fromstring(xml_data)
        titulos = []
        for item in root.findall(".//item")[:4]:
            titulo = item.find("title")
            if titulo is not None and titulo.text:
                titulos.append(titulo.text)
        if titulos:
            return "Últimas manchetes do InfoMoney: " + ". ".join(titulos)
    return None


# Códigos de tempo WMO usados pela Open-Meteo → descrição em português.
# Tabela oficial: https://open-meteo.com/en/docs (campo weather_code).
_DESCRICOES_CLIMA_WMO = {
    0: "céu limpo", 1: "predominantemente limpo", 2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina com geada",
    51: "garoa fraca", 53: "garoa moderada", 55: "garoa forte",
    56: "garoa congelante fraca", 57: "garoa congelante forte",
    61: "chuva fraca", 63: "chuva moderada", 65: "chuva forte",
    66: "chuva congelante fraca", 67: "chuva congelante forte",
    71: "neve fraca", 73: "neve moderada", 75: "neve forte", 77: "grãos de neve",
    80: "pancadas de chuva fracas", 81: "pancadas de chuva moderadas", 82: "pancadas de chuva violentas",
    85: "pancadas de neve fracas", 86: "pancadas de neve fortes",
    95: "trovoada", 96: "trovoada com granizo fraco", 99: "trovoada com granizo forte",
}


def _buscar_clima() -> str:
    # wttr.in é o serviço original, mas costuma ficar fora do ar (erro 500
    # recorrente, independente da cidade) — Open-Meteo é gratuito, sem chave
    # e mais estável; busca por lat/lon em vez de nome de cidade.
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={config.CIDADE_CLIMA_LAT}&longitude={config.CIDADE_CLIMA_LON}"
        "&current=temperature_2m,apparent_temperature,weather_code&timezone=auto"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as resposta:
        atual = json.loads(resposta.read().decode())["current"]
        condicao = _DESCRICOES_CLIMA_WMO.get(atual["weather_code"], "condição indisponível")
        return (
            f"Local: {config.CIDADE_CLIMA_LABEL}. Temperatura atual: {atual['temperature_2m']}°C. "
            f"Sensação térmica: {atual['apparent_temperature']}°C. Condição: {condicao}."
        )


def _busca_duckduckgo(pergunta: str) -> str | None:
    # API "Instant Answer" do DuckDuckGo: só devolve algo quando a pergunta
    # bate com um tópico no infobox/base de conhecimento deles — não é busca
    # real (scraping do html.duckduckgo.com foi tentado e bloqueado por
    # detecção de bot/anomaly da própria DuckDuckGo, sem sessão/JS de browser
    # de verdade). Por isso serve só como primeira tentativa rápida; ver
    # `_busca_wikipedia` como fallback pra conhecimento geral.
    url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(pergunta)}&format=json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as resposta:
        dados = json.loads(resposta.read().decode())
        resultado = dados.get("AbstractText", "")
        if not resultado:
            for topico in dados.get("RelatedTopics", []):
                if "Text" in topico:
                    resultado = topico["Text"]
                    break
        if resultado.strip():
            return resultado[:500]
    return None


_PREFIXOS_PERGUNTA = (
    "quem foi", "quem é", "quem era", "quem são",
    "o que é", "o que foi", "o que são", "o que significa",
)


def _termo_busca_wikipedia(pergunta: str) -> str:
    # O opensearch da Wikipédia é busca por prefixo de título, não entende
    # pergunta em linguagem natural — "quem foi machado de assis" não bate
    # com o artigo "Machado de Assis", mas "machado de assis" bate. Tira só
    # os prefixos de pergunta mais comuns; não tenta virar um parser de NLU.
    termo = pergunta.strip().rstrip("?").strip()
    termo_lower = termo.lower()
    for prefixo in _PREFIXOS_PERGUNTA:
        if termo_lower.startswith(prefixo):
            return termo[len(prefixo):].strip()
    return termo


def _busca_wikipedia(pergunta: str) -> str | None:
    """Fallback de conhecimento geral: acha o artigo mais relevante da
    Wikipédia em português (opensearch) e devolve o resumo dele (REST
    summary). Cobre bem definições e fatos enciclopédicos — não serve pra
    eventos muito recentes, mas é bem mais confiável que o Instant Answer do
    DuckDuckGo, que fica vazio pra maioria das perguntas gerais.
    """
    busca_url = (
        "https://pt.wikipedia.org/w/api.php?action=opensearch&limit=1&format=json&search="
        + urllib.parse.quote(_termo_busca_wikipedia(pergunta))
    )
    req = urllib.request.Request(busca_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=8) as resposta:
        titulos = json.loads(resposta.read().decode())[1]
    if not titulos:
        return None

    resumo_url = "https://pt.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(titulos[0])
    req_resumo = urllib.request.Request(resumo_url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req_resumo, timeout=8) as resposta_resumo:
        extrato = json.loads(resposta_resumo.read().decode()).get("extract", "")
    if extrato.strip():
        return extrato[:500]
    return None


def _busca_geral(pergunta: str) -> str | None:
    resultado = _busca_duckduckgo(pergunta)
    if resultado:
        return resultado
    try:
        return _busca_wikipedia(pergunta)
    except Exception:
        return None


def buscar_video_youtube(consulta: str) -> dict | None:
    """Busca o primeiro resultado de vídeo no YouTube para uma consulta e
    devolve a URL direta pra ele (que já começa a tocar sozinha ao abrir,
    sem precisar clicar em nada) e o título real do vídeo encontrado.

    Não usa a API oficial do YouTube (exigiria uma chave própria/quota) —
    extrai o primeiro `videoId` de um resultado de busca real
    (`videoRenderer`), direto do HTML que a própria página de resultados usa
    pra montar a lista. É uma heurística de "primeiro resultado": em buscas
    ambíguas (nome de música incompleto, várias versões/covers) pode achar
    um vídeo relacionado em vez do exato — mesma limitação que qualquer
    "toca o primeiro resultado" tem.
    """
    try:
        url_busca = "https://www.youtube.com/results?search_query=" + urllib.parse.quote(consulta)
        req = urllib.request.Request(url_busca, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as resposta:
            html = resposta.read().decode("utf-8", errors="ignore")

        match = re.search(r'"videoRenderer":\{"videoId":"([\w-]{11})"', html)
        if not match:
            return None
        video_id = match.group(1)
        video_url = f"https://www.youtube.com/watch?v={video_id}"

        titulo = consulta
        try:
            oembed_url = "https://www.youtube.com/oembed?url=" + urllib.parse.quote(video_url) + "&format=json"
            req_titulo = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req_titulo, timeout=5) as resp_titulo:
                titulo = json.loads(resp_titulo.read().decode()).get("title", consulta)
        except Exception:
            pass  # sem título real disponível, usa a própria consulta como fallback

        return {"url": video_url, "titulo": titulo}
    except Exception:
        return None


def buscar_na_internet(pergunta: str) -> str:
    pergunta_lower = pergunta.lower()
    try:
        if any(p in pergunta_lower for p in ["infomoney", "economia", "notícia", "noticia"]):
            resultado = _buscar_noticias()
            if resultado:
                return resultado

        if any(p in pergunta_lower for p in ["clima", "temperatura", "tempo", "previsão", "previsao"]):
            return _buscar_clima()

        resultado = _busca_geral(pergunta)
        if resultado:
            return resultado
    except Exception:
        pass
    return "Não consegui acessar os dados em tempo real no momento, senhor."
