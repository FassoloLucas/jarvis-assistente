# Cliente Flutter do J.A.R.V.I.S.

Interface móvel para o backend FastAPI: login, chat, voz, histórico e personalização. Consulte o README da raiz para instalação, variáveis e limitações.

Execute a partir desta pasta com backend próprio:

```powershell
flutter pub get
flutter run --dart-define=JARVIS_BACKEND_URL=http://10.0.2.2:8000
```

O exemplo aponta ao PC a partir do emulador Android padrão. Para dispositivo físico use um endereço acessível, respeitando as políticas de HTTP/HTTPS da plataforma. Nenhuma credencial ou hospedagem pessoal é fornecida. APKs e arquivos gerados devem ser produzidos na sua instalação; esta publicação não fez builds.
