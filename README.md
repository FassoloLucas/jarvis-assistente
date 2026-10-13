# J.A.R.V.I.S. — assistente de voz e automação

Protótipo de assistente pessoal com interface HUD no Windows, reconhecimento e síntese de voz, ferramentas de automação do PC, memória opcional, backend FastAPI e cliente Flutter. Demonstra integração de LLMs com ferramentas e uma interface móvel; não é um serviço pronto para produção.

Esta é uma edição pública com perfil neutro e configuração independente. O histórico privado, memórias, credenciais e instalações originais foram preservados e não estão neste repositório.

## Componentes

- `javis.py` inicia `jarvis/main.py`: HUD pywebview, cérebro, ativação por voz e ferramentas.
- `jarvis/brain.py` usa chamadas estruturadas de ferramentas via OpenRouter; `tools.py` executa ações como visão de tela, busca e automação.
- `jarvis/audio.py` e `wakeword.py`: transcrição por serviços de voz e fala com edge-tts/pygame. Não é um sistema totalmente offline.
- `jarvis/memoria.py`: memória opcional MongoDB; `calendario.py`: Google Calendar com OAuth próprio.
- `backend/`: cadastro/login JWT, conversas MongoDB, chat, fala e conexão WebSocket do agente PC.
- `app/`: Flutter com login, chat, voz, tema e fluxo de atualização Android.

## Demonstração pequena: desktop

Pré-requisitos: Windows, Python 3.10+ pela sintaxe utilizada, microfone/saída de áudio, internet, WebView2 para o HUD e uma chave própria OpenRouter. Dependências nativas, especialmente PyAudio, podem exigir preparação conforme sua versão do Python. Nenhuma instalação foi testada nesta publicação.

```powershell
git clone https://github.com/FassoloLucas/jarvis-assistente.git
cd jarvis-assistente
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Preencha apenas `OPENROUTER_API_KEY` para começar. `JARVIS_MODEL_ID` permite escolher um modelo disponível na sua conta. O exemplo fornece perfil neutro: nome/e-mail e cidade para clima podem ser configurados em `JARVIS_NOME`, `JARVIS_EMAIL` e `JARVIS_CLIMA_*`.

```powershell
.\.venv\Scripts\python.exe javis.py
```

Diga Jarvis e faça uma pergunta simples, por exemplo sobre data/hora. Comece sem calendário, memória, biometria, ar-condicionado ou controle remoto. O modelo decide chamar ferramentas; resultados dependem dos serviços e da configuração. Feche a janela para encerrar.

## Backend e cliente Flutter

Para o fluxo móvel, configure também uma conexão MongoDB própria em `MONGODB_URI`, `MONGODB_DB` e um `JARVIS_JWT_SECRET` aleatório longo em seu `.env`. O backend recusa inicialização sem segredo JWT; não há senha compartilhada de demonstração. Restrinja o acesso ao banco às redes necessárias. O chat requer OpenRouter.

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

A API local oferece documentação em `http://127.0.0.1:8000/docs`. O cliente permite cadastro e login com sua própria conta. Pré-requisitos do app: Flutter com Dart que satisfaça `^3.13.1`, conforme `app/pubspec.yaml`, Android SDK e dispositivo/emulador de desenvolvimento.

```powershell
cd app
flutter pub get
flutter run --dart-define=JARVIS_BACKEND_URL=http://10.0.2.2:8000
```

`10.0.2.2` é o endereço de acesso ao PC no emulador Android padrão. Para celular físico, configure URL acessível ao aparelho, preferencialmente HTTPS. Loopback do celular não aponta para o PC. Políticas de HTTP do Android/iOS podem exigir ajuste para desenvolvimento; a publicação não habilita tráfego inseguro de produção.

O endereço é fornecido por `--dart-define`, sem apontar para a hospedagem pessoal do autor. O fluxo de atualização consulta `/versao` e `/apk/latest`, mas não há APK distribuído: para utilizá-lo, hospede seu próprio APK compatível e ajuste `backend/versao.py`. Os arquivos de plataforma são os do projeto existente; plataformas além de Android não foram validadas.

## Recursos opcionais

- Memória: configure MongoDB. A coleção é compartilhada entre usuários que apontam ao mesmo banco; não armazene informações privadas em uma demonstração compartilhada. O prompt pode salvar fatos automaticamente.
- Calendário: crie credenciais OAuth de aplicativo desktop na sua conta Google, habilite Calendar API e salve `jarvis/data/google_credentials.json`; execute `setup_google_calendar.py` e autorize sua própria conta. Tokens ficam locais e ignorados.
- Biometria: `setup_perfil_vocal.py` usa Resemblyzer, torch e soundfile; esses extras não fazem parte da demonstração básica. O perfil local não é publicado e falhas podem deixar comandos passar: não é uma barreira de segurança.
- ConnectLife: `setup_connectlife.py` cadastra sua própria conta/dispositivo. As propriedades de `ar_condicionado.py` são específicas do modelo original e precisam de revisão para outros aparelhos.
- Agente PC: `jarvis/relay.py` lê `jarvis/data/relay_credentials.json` com `url_backend`, `email` e `senha` próprios; requer os extras requests e websocket-client. Sem esse arquivo, o relay fica desligado. Esse recurso permite automação remota: limite-o a ambiente confiável.

## Limitações e solução de problemas

Áudio e capturas de tela podem ser enviados a serviços externos. As ferramentas podem interagir com aplicativos e digitar no computador; demonstre em um ambiente controlado. O reconhecimento da palavra Jarvis usa transcrição externa em rajadas, com custo/latência e requisitos de privacidade distintos de um detector local.

Memória compartilhada, ausência de limites de requisição e controles de autenticação ainda exigem revisão antes de hospedar como serviço público. Conta inválida no app: confira MongoDB, segredo JWT e URL. Falha de voz: confira microfone, permissões e PyAudio. Falha de modelo: confira chave, saldo e modelo disponível. Integrações opcionais não são configuradas por esta publicação.

Não foram publicados `.env`, perfil pessoal, tokens OAuth, credenciais ConnectLife/relay, banco/memórias, perfis biométricos, áudio, APKs, caches ou caminhos de SDK pessoais. Dependências extras do desktop estão descritas em `requirements.txt`; biometria e relay continuam opcionais. Código revisado estaticamente, sem execução, builds ou novas integrações externas.
