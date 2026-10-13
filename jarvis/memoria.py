"""Memória de longo prazo do J.A.R.V.I.S. — fatos que ele aprende sobre o
chefe (e, agora, sobre quem mais usar o Jarvis) ao longo das conversas.

Antes era um SQLite local (um arquivo por instalação); agora é uma coleção
no MongoDB Atlas (tier gratuito M0), acessada via `pymongo` — é o que faz
duas instalações do J.A.R.V.I.S. (a sua, a de outra pessoa) compartilharem
os mesmos fatos aprendidos: os dois processos leem/escrevem na mesma
coleção. (A API REST do Atlas foi descontinuada em set/2025, senão daria pra
acessar só com `urllib` como em `web.py` — por isso o driver de verdade.)

Ver o README ("Memória compartilhada") pra criar o cluster gratuito e
configurar `config.MONGODB_URI`/`MONGODB_DB`.

Diferente do `persona.PERFIL` (fatos fixos, definidos no código pelo
desenvolvedor, um por instalação), essa memória cresce sozinha: o modelo
decide, através das ferramentas `lembrar_disso` / `esquecer_isso` (veja
`tools.py`), o que vale guardar ou apagar. Tudo que está aqui é injetado de
volta no system prompt em toda conversa (`persona.montar_system_prompt()`).

`listar_todas()` roda nesse caminho crítico (é chamada toda vez que o
system prompt é montado, inclusive na inicialização, sem try/except em
volta) — por isso ela mesma engole qualquer falha de conexão e devolve `[]`
em vez de propagar: um MongoDB temporariamente fora do ar não pode derrubar
o programa inteiro. `salvar`/`buscar`/`remover`, por outro lado, propagam a
exceção — quem chama (os handlers de tool calling em `tools.py`) já captura
isso e devolve uma resposta falada amigável, o mesmo padrão usado pro Google
Calendar.

Um único `MongoClient` é reusado entre chamadas (module-level, criado sob
demanda) — ele já mantém um pool de conexões internamente, não precisa (nem
deve) reconectar a cada operação.

`pymongo`/`certifi`/`bson` só são importados dentro das funções que
precisam deles, nunca aqui no topo — mesmo motivo de `voz_biometria.py` e
`ar_condicionado.py`: essa instalação específica do J.A.R.V.I.S. pode não
ter essas libs (ex: rodando pelo Python global em vez da venv do projeto,
como já aconteceu na prática), e isso não pode derrubar o import do módulo
inteiro — só faz essa funcionalidade específica falhar quando de fato usada.
"""

import re
from typing import TYPE_CHECKING, Optional

from . import config

if TYPE_CHECKING:
    from pymongo import MongoClient

_cliente: "Optional[MongoClient]" = None


def _colecao():
    global _cliente
    if _cliente is None:
        import certifi
        from pymongo import MongoClient

        # tlsCAFile explícito porque, no Windows, o pymongo não carrega o
        # repositório de certificados do sistema sozinho (o caminho padrão
        # que ele tenta, C:\Program Files\Common Files\SSL\cert.pem, nem
        # existe aqui) — sem isso, o handshake TLS falha com um erro
        # genérico ("TLSV1_ALERT_INTERNAL_ERROR") que não deixa claro que é
        # um problema de certificado.
        _cliente = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=8000, tlsCAFile=certifi.where())
    return _cliente[config.MONGODB_DB]["memorias"]


def salvar(fato: str, categoria: str | None = None) -> dict:
    """Guarda um fato novo. Se um fato idêntico (mesmo texto, sem diferenciar
    maiúsculas/minúsculas) já existir, não duplica."""
    fato = fato.strip()
    colecao = _colecao()
    existente = colecao.find_one({"fato": {"$regex": f"^{re.escape(fato)}$", "$options": "i"}})
    if existente:
        return {"novo": False, "id": str(existente["_id"])}

    resultado = colecao.insert_one({"fato": fato, "categoria": categoria})
    return {"novo": True, "id": str(resultado.inserted_id)}


def listar_todas(limite: int = 200) -> list[dict]:
    """Devolve as memórias mais recentes (até `limite`), em ordem cronológica.
    Devolve lista vazia (em vez de propagar erro) se o MongoDB não estiver
    configurado ou estiver inacessível — ver docstring do módulo."""
    if not config.MONGODB_URI:
        return []
    try:
        documentos = list(_colecao().find().sort("_id", -1).limit(limite))
    except Exception as e:
        # Exceção genérica de propósito (não só PyMongoError): isso também
        # cobre a lib nem estar instalada nessa instalação (ver docstring do
        # módulo) — de qualquer forma, esse caminho nunca pode propagar.
        print(f"Memória compartilhada indisponível agora: {e}")
        return []
    return [
        {"id": str(d["_id"]), "fato": d["fato"], "categoria": d.get("categoria")}
        for d in reversed(documentos)
    ]


def buscar(descricao: str) -> list[dict]:
    """Busca aproximada por conteúdo — usada por `esquecer_isso`, já que o
    modelo descreve o que quer esquecer em linguagem natural, não por id.
    Tenta a frase inteira primeiro; se não achar nada, tenta palavra por
    palavra (ignorando as bem curtas)."""
    colecao = _colecao()
    documentos = list(colecao.find({"fato": {"$regex": re.escape(descricao), "$options": "i"}}))
    if not documentos:
        for palavra in [p for p in descricao.split() if len(p) > 3]:
            documentos = list(colecao.find({"fato": {"$regex": re.escape(palavra), "$options": "i"}}))
            if documentos:
                break
    return [{"id": str(d["_id"]), "fato": d["fato"]} for d in documentos]


def remover(id_memoria: str) -> bool:
    from bson import ObjectId

    resultado = _colecao().delete_one({"_id": ObjectId(id_memoria)})
    return resultado.deleted_count > 0
