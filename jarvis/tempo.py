"""Formatação de data/hora em português, sem depender do locale do sistema
operacional — `locale.setlocale("pt_BR")` costuma falhar em instalações
Windows que não têm esse locale instalado, o que faria dia da semana/mês
saírem em inglês no meio de um prompt em português. Mapeamento manual
evita essa dependência frágil.
"""

from datetime import datetime

_DIAS_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
]
_MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def agora_por_extenso() -> str:
    """Ex: 'domingo, 9 de agosto de 2026, 14:32'. Usado pra dar ao modelo
    consciência de data/hora atual sem precisar de uma ferramenta/rodada
    extra — é injetado fresco a cada pergunta (veja brain.py), então nunca
    fica desatualizado numa sessão longa."""
    agora = datetime.now()
    dia_semana = _DIAS_SEMANA[agora.weekday()]
    mes = _MESES[agora.month - 1]
    return f"{dia_semana}, {agora.day} de {mes} de {agora.year}, {agora.strftime('%H:%M')}"
