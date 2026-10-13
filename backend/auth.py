"""Autenticação do backend — cadastro/login com e-mail/senha, sessão via
JWT. Simples de propósito: são só duas pessoas usando isso, não justifica
um provedor de auth externo (Auth0, Firebase Auth etc.) pra esse tamanho.

A chave de assinatura do JWT vem de uma variável de ambiente
(`JARVIS_JWT_SECRET`), não de `config.py` como o resto das credenciais do
projeto — diferente delas, essa chave não precisa ser a mesma entre
ambientes (local vs. hospedado) e não faz sentido versionar junto com o
código de jeito nenhum (qualquer um com ela forja login de qualquer conta).
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

_SEGREDO_JWT = os.environ.get("JARVIS_JWT_SECRET", "")
if not _SEGREDO_JWT:
    raise RuntimeError("Defina JARVIS_JWT_SECRET antes de iniciar o backend.")
_ALGORITMO = "HS256"
_VALIDADE_TOKEN = timedelta(days=30)

_cliente_mongo = None


def _usuarios():
    global _cliente_mongo
    from jarvis import config

    if _cliente_mongo is None:
        import certifi
        from pymongo import MongoClient

        _cliente_mongo = MongoClient(config.MONGODB_URI, serverSelectionTimeoutMS=8000, tlsCAFile=certifi.where())
    return _cliente_mongo[config.MONGODB_DB]["usuarios"]


def registrar(email: str, senha: str, nome: str) -> dict:
    import bcrypt

    email = email.strip().lower()
    if _usuarios().find_one({"email": email}):
        raise ValueError("Já existe uma conta com esse e-mail.")

    hash_senha = bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    resultado = _usuarios().insert_one({"email": email, "senha_hash": hash_senha, "nome": nome})
    return {"id": str(resultado.inserted_id), "email": email, "nome": nome}


def autenticar(email: str, senha: str) -> Optional[dict]:
    import bcrypt

    usuario = _usuarios().find_one({"email": email.strip().lower()})
    if not usuario or not bcrypt.checkpw(senha.encode("utf-8"), usuario["senha_hash"].encode("utf-8")):
        return None
    return usuario


def gerar_token(usuario: dict) -> str:
    import jwt

    payload = {
        "sub": str(usuario["_id"]),
        "email": usuario["email"],
        "nome": usuario.get("nome"),
        "exp": datetime.now(timezone.utc) + _VALIDADE_TOKEN,
    }
    return jwt.encode(payload, _SEGREDO_JWT, algorithm=_ALGORITMO)


def verificar_token(token: str) -> dict:
    import jwt

    return jwt.decode(token, _SEGREDO_JWT, algorithms=[_ALGORITMO])
