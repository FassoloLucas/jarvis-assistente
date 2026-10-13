"""Autoriza o acesso do J.A.R.V.I.S. ao seu Google Calendar — roda uma
única vez, de propósito, em vez de deixar o primeiro comando de voz que
usa a agenda disparar um navegador no meio da conversa sem aviso.

Pré-requisito: ter salvo o JSON de credenciais OAuth em
jarvis/data/google_credentials.json (veja o README pra gerar o seu no
Google Cloud Console).

Uso:
    python setup_google_calendar.py
"""

from jarvis import calendario


def main():
    print("Abrindo o navegador para autorizar o acesso ao Google Calendar...")
    calendario._autenticar()
    print(f"Pronto! Token salvo em {calendario.CAMINHO_TOKEN}.")
    print("Testando o acesso: listando os próximos compromissos...")
    eventos = calendario.listar_proximos_eventos(dias_a_frente=14)
    if not eventos:
        print("Nenhum compromisso encontrado nos próximos 14 dias (ou a agenda está vazia).")
    else:
        for evento in eventos:
            print(f"- {evento['titulo']} — {evento['inicio']}")


if __name__ == "__main__":
    main()
