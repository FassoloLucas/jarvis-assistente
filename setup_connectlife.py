"""Cadastra o acesso à sua conta ConnectLife (Hisense, Gorenje, ASKO, ATAG,
ETNA Connect) pra o J.A.R.V.I.S. poder controlar seu ar condicionado. Roda
uma única vez (ou de novo se trocar de aparelho/conta).

ATENÇÃO: usa a biblioteca `connectlife` (github.com/oyvindwe/connectlife),
que fala com a API não-oficial da ConnectLife via engenharia reversa — não é
suportada nem sancionada pela ConnectLife/Hisense. Existe um risco pequeno
(mas real, avisado pelo próprio projeto) de a conta ser sinalizada ou
bloqueada por uso fora do app oficial.

Suas credenciais (e-mail/senha) ficam salvas em texto puro em
jarvis/data/connectlife_credentials.json — mesmo nível de proteção que o
resto das credenciais locais do projeto (ex: a chave da OpenRouter em
config.py). Nunca são enviadas pra lugar nenhum além da própria API da
ConnectLife.

Pré-requisito: dependências instaladas na venv do projeto:
    .venv\\Scripts\\pip install connectlife

Uso:
    .venv\\Scripts\\python.exe setup_connectlife.py
"""

import asyncio
import getpass
import json
from pathlib import Path

from connectlife.api import ConnectLifeApi

CAMINHO_CREDENCIAIS = Path(__file__).parent / "jarvis" / "data" / "connectlife_credentials.json"
CAMINHO_DUMP = Path(__file__).parent / "jarvis" / "data" / "connectlife_dump.json"


async def main_async() -> None:
    print("=== Cadastro da conta ConnectLife ===\n")
    email = input("E-mail da conta ConnectLife (o mesmo do app): ").strip()
    senha = getpass.getpass("Senha (não aparece na tela enquanto digita): ")

    api = ConnectLifeApi(email, senha)
    print("\nFazendo login...")
    if not await api.authenticate():
        print("Falha no login. Confira e-mail/senha (iguais aos do app) e tente de novo.")
        return

    print("Login OK! Buscando os aparelhos cadastrados na conta...")
    aparelhos = await api.get_appliances()
    if not aparelhos:
        print("Não encontrei nenhum aparelho nessa conta.")
        return

    print(f"\nEncontrei {len(aparelhos)} aparelho(s):")
    for i, aparelho in enumerate(aparelhos):
        print(
            f"  [{i}] {aparelho.device_nickname!r} — {aparelho.device_type_name} "
            f"(sala: {aparelho.room_name or '?'})"
        )

    indice = -1
    while not (0 <= indice < len(aparelhos)):
        try:
            indice = int(input("\nQual número é o ar condicionado que quer controlar? "))
        except ValueError:
            continue
    escolhido = aparelhos[indice]

    CAMINHO_CREDENCIAIS.parent.mkdir(parents=True, exist_ok=True)
    CAMINHO_CREDENCIAIS.write_text(
        json.dumps(
            {
                "email": email,
                "senha": senha,
                "puid": escolhido.puid,
                "device_type_code": escolhido.device_type_code,
                "device_feature_code": escolhido.device_feature_code,
                "apelido": escolhido.device_nickname,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\nCredenciais salvas em {CAMINHO_CREDENCIAIS}.")

    # Dump das propriedades atuais do aparelho escolhido — os nomes das
    # propriedades (qual chave é liga/desliga, temperatura, modo etc.) variam
    # por modelo e não são documentados publicamente; esse arquivo é o que
    # permite descobrir isso pra implementar o controle de verdade. Não tem
    # nenhuma credencial nele, só o estado atual do aparelho.
    dump = {chave: str(valor) for chave, valor in escolhido.status_list.items()}
    CAMINHO_DUMP.write_text(json.dumps(dump, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Dump das propriedades do aparelho salvo em {CAMINHO_DUMP}.")
    print("\nPronto! Agora é só avisar que terminou.")


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
