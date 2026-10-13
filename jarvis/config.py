"""Configurações globais do J.A.R.V.I.S.

Centraliza tudo que antes estava espalhado como literais soltos no meio do
código: credenciais, parâmetros do modelo, voz e interface.
"""

import os

from dotenv import load_dotenv

# Carrega jarvis/../.env (raiz do projeto) se existir — é onde ficam os
# segredos de verdade agora (chave da OpenRouter, connection string do
# MongoDB), fora do código e fora do git (.env está no .gitignore). O
# Render, hospedando o backend, não usa esse arquivo — configura as mesmas
# variáveis direto no painel dele. Sem .env e sem variável de ambiente
# nenhuma (ex: repositório clonado do zero, antes de configurar), essas
# duas ficam vazias — ver README pra instruções de setup.
load_dotenv()

# --- Conexão com o modelo (via OpenRouter) ---
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
MODEL_ID = os.environ.get("JARVIS_MODEL_ID", "openai/gpt-4o-mini")
TEMPERATURE = 0.7
MAX_RODADAS_TOOL_CALLING = 8  # limite de idas e vindas de ferramentas por comando, evita loop infinito

# --- Voz (TTS) ---
VOZ_TTS = "pt-BR-AntonioNeural"
TAXA_FALA = "+15%"

# --- Localização padrão para clima (Open-Meteo, busca por lat/lon) ---
CIDADE_CLIMA_LAT = float(os.environ.get("JARVIS_CLIMA_LAT", "-23.5505"))
CIDADE_CLIMA_LON = float(os.environ.get("JARVIS_CLIMA_LON", "-46.6333"))
CIDADE_CLIMA_LABEL = os.environ.get("JARVIS_CLIMA_CIDADE", "São Paulo, SP")

# --- Fontes de notícias ---
FEED_NOTICIAS = "https://www.infomoney.com.br/feed/"

# --- YouTube ---
# Tempo de espera (segundos) após abrir uma aba do YouTube antes de simular o
# atalho de play/pause — precisa ser grande o bastante pra aba carregar e
# ganhar foco antes do pyautogui mandar a tecla.
ATRASO_PLAY_YOUTUBE = 2.5

# --- Interface ---
JANELA_TITULO = "J.A.R.V.I.S. | Interface Core - Demonstração"
JANELA_GEOMETRIA = "700x600"

# --- Palavra de ativação ---
# Detecção via Google (mesmo mecanismo do resto do reconhecimento de voz) —
# sem precisar de conta/serviço novo. Escuta em rajadas curtas e verifica se
# a palavra abaixo apareceu na transcrição.
PALAVRA_CHAVE = "jarvis"
TEMPO_MAX_RAJADA_WAKE = 4  # segundos: duração máxima de cada rajada de escuta
FRASE_ATIVACAO = "Pois não, senhor. À sua disposição."

# Quantos segundos esperar por uma resposta de acompanhamento (ex: depois de
# "posso ajudar com mais alguma coisa?") antes de desistir e voltar a exigir
# "Jarvis" de novo.
TIMEOUT_CONTINUACAO = 6

# --- Memória compartilhada (MongoDB Atlas — veja jarvis/memoria.py) ---
# Mesma lógica de .env da chave da OpenRouter acima — essa string TEM a
# senha do banco dentro.
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB = os.environ.get("MONGODB_DB", "jarvis")

# --- Biometria de voz (opcional — veja jarvis/voz_biometria.py) ---
# Similaridade de cosseno mínima entre a voz de um comando e o perfil vocal
# cadastrado (setup_perfil_vocal.py) pra considerar que é o chefe falando.
# Só tem efeito depois de cadastrar um perfil; sem isso, é ignorado. Recusando
# o próprio chefe? Baixe um pouco. Aceitando outra voz? Suba.
LIMIAR_SIMILARIDADE_VOZ = 0.75
