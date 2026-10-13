"""Ferramentas (function/tool calling) do J.A.R.V.I.S.

Substitui o antigo esquema de tags de texto (`[ABRIR]`, `[SITE]`,
`[DIGITAR]`...) parseadas na marra com `if "[TAG]" in texto_resposta`.
Em vez do modelo "escrever" uma tag num texto livre — o que causava bugs
tipo uma resposta comum contendo ``` disparar o fluxo de "escrever código"
— ele agora chama uma função estruturada com argumentos validados por
JSON schema. `TOOLS` descreve o schema para a API; `TOOL_HANDLERS` mapeia
cada nome de ferramenta para o código Python que realmente a executa.

Cada handler recebe um dict de argumentos e devolve um dict com até três
chaves:
    - "fala": frase curta pra falar em voz alta antes/durante a execução (opcional)
    - "resultado": texto que volta pro modelo como resposta da tool call
    - "imagem": string base64 de uma captura de tela (só a `ver_tela` usa)
"""

import ctypes
import subprocess
import time
import webbrowser

from . import ar_condicionado, calendario, config, memoria, web
from .vision import tirar_print_base64

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "abrir_programa",
            "description": "Abre um programa, app ou jogo instalado no computador via busca do Windows.",
            "parameters": {
                "type": "object",
                "properties": {
                    "nome": {"type": "string", "description": "Nome do programa, ex: WhatsApp, Spotify, Riot Client"}
                },
                "required": ["nome"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "abrir_site",
            "description": (
                "Abre um site ou link no navegador padrão. Para tocar uma música específica no "
                "Spotify, use o formato spotify:search:nome_da_musica."
            ),
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "digitar_texto",
            "description": "Digita um texto na janela atualmente em foco (ex: barra de busca do WhatsApp).",
            "parameters": {
                "type": "object",
                "properties": {"texto": {"type": "string"}},
                "required": ["texto"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fechar_janela",
            "description": "Fecha o programa/janela atualmente em foco (Alt+F4).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "controlar_midia",
            "description": "Controla a reprodução de mídia (play/pause/próxima faixa/faixa anterior).",
            "parameters": {
                "type": "object",
                "properties": {"acao": {"type": "string", "enum": ["playpause", "nexttrack", "prevtrack"]}},
                "required": ["acao"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "controlar_volume",
            "description": "Ajusta o volume do sistema.",
            "parameters": {
                "type": "object",
                "properties": {"acao": {"type": "string", "enum": ["aumentar", "diminuir", "mutar"]}},
                "required": ["acao"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "escrever_codigo",
            "description": "Abre o Bloco de Notas e cola um código limpo, sem explicações nem formatação markdown.",
            "parameters": {
                "type": "object",
                "properties": {"codigo": {"type": "string"}},
                "required": ["codigo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gerar_rascunho",
            "description": "Abre o Bloco de Notas e cola uma explicação/resolução didática de uma questão vista na tela.",
            "parameters": {
                "type": "object",
                "properties": {"explicacao": {"type": "string"}},
                "required": ["explicacao"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tocar_video_youtube",
            "description": (
                "Busca algo no YouTube e abre direto no vídeo já em reprodução, sem precisar "
                "clicar em nada. Use sempre que o chefe pedir pra tocar, ouvir ou assistir algo "
                "no YouTube (música, artista, vídeo específico)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {"type": "string", "description": "O que buscar: nome da música, artista, vídeo, etc."}
                },
                "required": ["consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_agenda",
            "description": (
                "Lista os próximos compromissos da agenda de verdade do chefe (Google Calendar). "
                "Use quando ele perguntar o que tem marcado, sua agenda, compromissos, reuniões, etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "dias_a_frente": {
                        "type": "integer",
                        "description": "Quantos dias a partir de hoje considerar (padrão 7).",
                    }
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "criar_compromisso",
            "description": (
                "Cria um evento na agenda de verdade do chefe (Google Calendar). Calcule a "
                "data/hora exata em formato ISO 8601 (ex: '2026-08-10T15:00:00') com base na "
                "data e hora atuais informadas no início da conversa — nunca passe uma data "
                "relativa (tipo 'amanhã') direto pra ferramenta."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string"},
                    "inicio_iso": {
                        "type": "string",
                        "description": "Data/hora de início, ISO 8601, ex: 2026-08-10T15:00:00",
                    },
                    "fim_iso": {
                        "type": "string",
                        "description": "Data/hora de término, ISO 8601. Se omitido, assume 1 hora de duração.",
                    },
                    "local": {"type": "string"},
                    "descricao": {"type": "string"},
                },
                "required": ["titulo", "inicio_iso"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lembrar_disso",
            "description": (
                "Guarda um fato/preferência sobre o chefe na memória de longo prazo, pra lembrar "
                "em conversas futuras (inclusive depois de fechar e abrir o programa de novo). "
                "Use sempre que ele contar um gosto, rotina, evento ou preferência que valha a "
                "pena lembrar — não precisa que ele peça explicitamente."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "fato": {
                        "type": "string",
                        "description": "O fato em si, escrito de forma clara e independente (ex: 'Prefere café sem açúcar').",
                    },
                    "categoria": {
                        "type": "string",
                        "description": "Categoria opcional, ex: gosto, rotina, trabalho, evento, relacionamento.",
                    },
                },
                "required": ["fato"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "esquecer_isso",
            "description": (
                "Remove um fato da memória de longo prazo quando o chefe pedir pra esquecer ou "
                "corrigir algo que você sabe sobre ele."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "descricao": {
                        "type": "string",
                        "description": "Descrição do que esquecer, o mais parecida possível com o fato original.",
                    }
                },
                "required": ["descricao"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_web",
            "description": (
                "Busca informações em tempo real na internet: clima/temperatura, notícias do "
                "InfoMoney/economia, ou uma busca geral sobre qualquer outro assunto atual."
            ),
            "parameters": {
                "type": "object",
                "properties": {"consulta": {"type": "string"}},
                "required": ["consulta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ver_tela",
            "description": "Captura a tela atual para você analisar visualmente (ler contatos, resumir vídeo, ler uma questão, etc).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "controlar_ar_condicionado",
            "description": (
                "Controla o ar condicionado do quarto (via ConnectLife): ligar/desligar, ajustar "
                "temperatura, modo ou velocidade do vento. Pode combinar vários ajustes numa única "
                "chamada (ex: ligar e já colocar 22 graus no frio)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ligado": {
                        "type": "boolean",
                        "description": "true pra ligar, false pra desligar. Omita se só for mudar temperatura/modo/velocidade.",
                    },
                    "temperatura": {
                        "type": "integer",
                        "description": f"Temperatura em Celsius, entre {ar_condicionado.TEMP_MIN} e {ar_condicionado.TEMP_MAX}.",
                    },
                    "modo": {"type": "string", "enum": list(ar_condicionado.MODOS)},
                    "velocidade": {"type": "string", "enum": list(ar_condicionado.VELOCIDADES)},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_ar_condicionado",
            "description": "Consulta o estado atual do ar condicionado do quarto (ligado/desligado, temperatura, modo, velocidade).",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

def _colar_no_bloco_de_notas(texto: str) -> None:
    # Import tardio: pyautogui/pyperclip precisam de um display de verdade
    # (X11/etc) — o backend (Render, Linux headless) também importa este
    # módulo pra pegar TOOL_HANDLERS, mesmo nunca chamando essas funções
    # PC-only (ver tools.FERRAMENTAS_NUVEM).
    import pyautogui
    import pyperclip

    texto = texto.strip()
    for cerca in ("```python", "```html", "```"):
        texto = texto.replace(cerca, "")

    subprocess.Popen(["notepad.exe"])
    time.sleep(2)  # espera o Notepad abrir e ganhar foco

    pyperclip.copy(texto)
    time.sleep(0.5)
    pyautogui.hotkey("ctrl", "v")


def _abrir_programa(args: dict) -> dict:
    import pyautogui

    nome = args["nome"]
    pyautogui.press("win")
    time.sleep(0.5)
    pyautogui.write(nome, interval=0.03)
    time.sleep(0.5)
    pyautogui.press("enter")
    return {"fala": f"Iniciando {nome}.", "resultado": f"{nome} foi aberto."}


def _abrir_site(args: dict) -> dict:
    url = args["url"]
    webbrowser.open(url)
    # Sem a URL no resultado de propósito — mesmo motivo do criar_compromisso.
    return {"fala": "Acessando a rede.", "resultado": "Site aberto no navegador com sucesso."}


def _digitar_texto(args: dict) -> dict:
    import pyautogui

    texto = args["texto"]
    time.sleep(1)
    pyautogui.write(texto, interval=0.03)
    return {"fala": "Registrando os dados.", "resultado": f"Texto digitado: {texto!r}."}


def _titulo_janela_ativa() -> str:
    hwnd = ctypes.windll.user32.GetForegroundWindow()
    comprimento = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(comprimento + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, comprimento + 1)
    return buffer.value


def _fechar_janela(_args: dict) -> dict:
    import pyautogui

    # Alt+F4 fecha a janela que estiver em foco — sem essa checagem, se o
    # próprio HUD do J.A.R.V.I.S. (jarvis/ui.py) estivesse em foco quando
    # essa ferramenta fosse chamada, ele se fecharia sozinho.
    if "J.A.R.V.I.S" in _titulo_janela_ativa():
        return {
            "fala": "Essa é a minha própria janela, chefe. Diz qual programa você quer fechar.",
            "resultado": "Recusado: a janela em foco era o próprio J.A.R.V.I.S., nada foi fechado.",
        }
    pyautogui.hotkey("alt", "f4")
    return {"fala": "Limpando a tela.", "resultado": "Janela fechada."}


def _controlar_midia(args: dict) -> dict:
    import pyautogui

    acao = args["acao"]
    pyautogui.press(acao)
    return {"fala": "Comando de áudio acionado.", "resultado": f"Mídia: {acao}."}


_TECLAS_VOLUME = {"aumentar": "volumeup", "diminuir": "volumedown", "mutar": "volumemute"}


def _controlar_volume(args: dict) -> dict:
    import pyautogui

    acao = args["acao"]
    tecla = _TECLAS_VOLUME[acao]
    repeticoes = 5 if tecla in ("volumeup", "volumedown") else 1
    for _ in range(repeticoes):
        pyautogui.press(tecla)
    return {"fala": "Reconfigurando os canais de áudio.", "resultado": f"Volume: {acao}."}


def _escrever_codigo(args: dict) -> dict:
    _colar_no_bloco_de_notas(args["codigo"])
    return {"fala": "Escrevendo o código solicitado, chefe.", "resultado": "Código colado no Bloco de Notas."}


def _gerar_rascunho(args: dict) -> dict:
    _colar_no_bloco_de_notas(args["explicacao"])
    return {
        "fala": "Analisando a questão da tela. Gerando o passo a passo da resolução no seu bloco de notas, chefe.",
        "resultado": "Explicação colada no Bloco de Notas.",
    }


def _tocar_video_youtube(args: dict) -> dict:
    import pyautogui

    consulta = args["consulta"]
    resultado = web.buscar_video_youtube(consulta)
    if not resultado:
        return {
            "fala": "Não encontrei nada no YouTube pra essa busca, chefe.",
            "resultado": f"Nenhum resultado encontrado no YouTube para '{consulta}'.",
        }
    webbrowser.open(resultado["url"])

    # A maioria dos navegadores bloqueia autoplay com som em abas abertas por
    # fora (sem gesto do usuário naquela aba) — o vídeo carrega pausado. Como
    # não dá pra rodar JS no navegador padrão do usuário (só na janela do
    # próprio HUD), simulamos o atalho de teclado do YouTube (K = play/pause)
    # assim que a aba termina de carregar e ganha foco.
    time.sleep(config.ATRASO_PLAY_YOUTUBE)
    pyautogui.press("k")

    return {
        "fala": f"Tocando no YouTube: {resultado['titulo']}.",
        # Sem a URL aqui de propósito — mesmo motivo do criar_compromisso:
        # o modelo não pode ler em voz alta um link que nunca recebeu.
        "resultado": f"Vídeo aberto e em reprodução: {resultado['titulo']}.",
    }


def _consultar_agenda(args: dict) -> dict:
    dias = args.get("dias_a_frente") or 7
    try:
        eventos = calendario.listar_proximos_eventos(dias_a_frente=dias)
    except Exception as e:
        return {"resultado": f"Não consegui acessar o Google Calendar agora: {e}"}
    if not eventos:
        return {"resultado": f"Nenhum compromisso encontrado nos próximos {dias} dias."}
    linhas = "; ".join(f"{e['titulo']} em {e['inicio']}" for e in eventos)
    return {"resultado": f"Compromissos encontrados: {linhas}"}


def _criar_compromisso(args: dict) -> dict:
    try:
        resultado = calendario.criar_evento(
            titulo=args["titulo"],
            inicio_iso=args["inicio_iso"],
            fim_iso=args.get("fim_iso"),
            descricao=args.get("descricao"),
            local=args.get("local"),
        )
    except Exception as e:
        return {
            "fala": "Não consegui criar o compromisso na agenda, chefe.",
            "resultado": f"Erro ao criar evento: {e}",
        }
    # De propósito, não devolvemos o link (resultado["link"]) pro modelo: ele
    # não tem como ler em voz alta uma URL que nunca recebeu. Ver também a
    # regra geral em persona.INSTRUCOES_COMPORTAMENTO, como segunda camada.
    return {
        "fala": f"Compromisso {args['titulo']!r} criado na agenda, chefe.",
        "resultado": f"Evento {args['titulo']!r} criado com sucesso na agenda (id: {resultado['id']}).",
    }


def _lembrar_disso(args: dict) -> dict:
    fato = args["fato"]
    # Antes (SQLite local) praticamente nunca falhava; agora é uma chamada de
    # rede pro MongoDB compartilhado, que pode estar fora do ar/sem conexão.
    try:
        resultado = memoria.salvar(fato, args.get("categoria"))
    except Exception as e:
        return {
            "fala": "Não consegui salvar isso na memória compartilhada agora, chefe.",
            "resultado": f"Erro ao salvar na memória: {e}",
        }
    if resultado["novo"]:
        return {"resultado": f"Fato salvo na memória de longo prazo: {fato!r}."}
    return {"resultado": f"Esse fato já estava salvo, não duplicou: {fato!r}."}


def _esquecer_isso(args: dict) -> dict:
    try:
        candidatos = memoria.buscar(args["descricao"])
    except Exception as e:
        return {
            "fala": "Não consegui acessar a memória compartilhada agora, chefe.",
            "resultado": f"Erro ao buscar na memória: {e}",
        }
    if not candidatos:
        return {"resultado": f"Não encontrei na memória nada parecido com {args['descricao']!r}."}
    if len(candidatos) > 1:
        lista = "; ".join(f"[{c['id']}] {c['fato']}" for c in candidatos)
        return {
            "resultado": (
                f"Encontrei mais de um fato parecido, peça pro chefe especificar qual: {lista}"
            )
        }
    try:
        memoria.remover(candidatos[0]["id"])
    except Exception as e:
        return {
            "fala": "Não consegui remover isso da memória compartilhada agora, chefe.",
            "resultado": f"Erro ao remover da memória: {e}",
        }
    return {"resultado": f"Removido da memória: {candidatos[0]['fato']!r}."}


def _buscar_web(args: dict) -> dict:
    resultado = web.buscar_na_internet(args["consulta"])
    # Sem "fala" aqui de propósito: a resposta falada final é formulada pelo
    # modelo na próxima rodada, com base neste resultado.
    return {"resultado": resultado}


def _ver_tela(_args: dict) -> dict:
    imagem = tirar_print_base64()
    return {"resultado": "Captura de tela realizada.", "imagem": imagem}


def _controlar_ar_condicionado(args: dict) -> dict:
    if not ar_condicionado.configurado():
        import os

        print(
            f"AC não configurado — arquivo_local={ar_condicionado.CAMINHO_CREDENCIAIS.exists()}, "
            f"env_vars={ {v: bool(os.environ.get(v)) for v in ar_condicionado._VARS_AMBIENTE} }"
        )
        return {
            "fala": "Ainda não tenho acesso ao ar condicionado, chefe.",
            "resultado": "Ar condicionado não cadastrado (rode setup_connectlife.py).",
        }
    ajustes = []
    try:
        if "ligado" in args:
            ajustes.append(ar_condicionado.ligar(args["ligado"]))
        if args.get("temperatura") is not None:
            ajustes.append(f"{ar_condicionado.definir_temperatura(args['temperatura'])}°C")
        if args.get("modo"):
            ajustes.append(f"modo {ar_condicionado.definir_modo(args['modo'])}")
        if args.get("velocidade"):
            ajustes.append(f"velocidade {ar_condicionado.definir_velocidade(args['velocidade'])}")
    except Exception as e:
        # Log de verdade — sem isso, o erro só existe como texto dentro da
        # conversa com o modelo, nunca aparece em log nenhum (nem desktop
        # nem backend hospedado).
        print(f"Erro ao controlar o ar condicionado (args={args}): {e!r}")
        return {
            "fala": "Não consegui falar com o ar condicionado agora, chefe.",
            "resultado": f"Erro ao controlar o ar condicionado: {e}",
        }
    if not ajustes:
        return {"resultado": "Nenhum ajuste foi pedido pro ar condicionado."}
    return {"fala": "Ajustando o ar condicionado.", "resultado": f"Ar condicionado: {', '.join(ajustes)}."}


def _consultar_ar_condicionado(_args: dict) -> dict:
    if not ar_condicionado.configurado():
        return {"resultado": "Ar condicionado não cadastrado (rode setup_connectlife.py)."}
    try:
        estado = ar_condicionado.status()
    except Exception as e:
        return {"resultado": f"Não consegui consultar o ar condicionado agora: {e}"}
    if not estado["ligado"]:
        return {"resultado": "O ar condicionado está desligado."}
    return {
        "resultado": (
            f"Ar condicionado ligado, modo {estado['modo']}, alvo {estado['temperatura']}°C, "
            f"velocidade {estado['velocidade']}, temperatura ambiente {estado['temperatura_ambiente']}°C."
        )
    }


TOOL_HANDLERS = {
    "abrir_programa": _abrir_programa,
    "abrir_site": _abrir_site,
    "digitar_texto": _digitar_texto,
    "fechar_janela": _fechar_janela,
    "controlar_midia": _controlar_midia,
    "controlar_volume": _controlar_volume,
    "escrever_codigo": _escrever_codigo,
    "gerar_rascunho": _gerar_rascunho,
    "tocar_video_youtube": _tocar_video_youtube,
    "consultar_agenda": _consultar_agenda,
    "criar_compromisso": _criar_compromisso,
    "lembrar_disso": _lembrar_disso,
    "esquecer_isso": _esquecer_isso,
    "buscar_web": _buscar_web,
    "ver_tela": _ver_tela,
    "controlar_ar_condicionado": _controlar_ar_condicionado,
    "consultar_ar_condicionado": _consultar_ar_condicionado,
}

# Ferramentas que mudam a memória de longo prazo — quando alguma delas é
# chamada, o brain.py recarrega o system prompt na hora (veja brain.py),
# pra já refletir o aprendizado dentro da mesma sessão, sem precisar
# reiniciar o programa.
FERRAMENTAS_QUE_MUDAM_MEMORIA = {"lembrar_disso", "esquecer_isso"}

# Ferramentas que não dependem do PC do chefe estar ligado (só chamam APIs
# externas) — essas ficam disponíveis pro backend do app de celular mesmo
# sem o relay de controle remoto (fase 5) conectado. As demais
# (abrir_programa, digitar_texto, fechar_janela, controlar_midia,
# controlar_volume, escrever_codigo, gerar_rascunho, tocar_video_youtube,
# ver_tela) só fazem sentido executando localmente no PC — precisam do
# relay pra funcionar a partir do celular.
FERRAMENTAS_NUVEM = {
    "buscar_web",
    "consultar_agenda",
    "criar_compromisso",
    "lembrar_disso",
    "esquecer_isso",
    "controlar_ar_condicionado",
    "consultar_ar_condicionado",
}
