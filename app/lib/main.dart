import 'package:flutter/material.dart';
import 'servicos/api.dart';
import 'servicos/atualizador.dart';
import 'servicos/tema.dart';
import 'telas/atualizacao_tela.dart';
import 'telas/chat_tela.dart';
import 'telas/login_tela.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await TemaServico.carregar();
  runApp(const JarvisApp());
}

class JarvisApp extends StatelessWidget {
  const JarvisApp({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<Color>(
      valueListenable: TemaServico.corDestaque,
      builder: (context, corDestaque, _) {
        return MaterialApp(
          title: 'J.A.R.V.I.S.',
          debugShowCheckedModeBanner: false,
          theme: TemaServico.montarTema(corDestaque),
          home: _PortaEntrada(api: ApiCliente()),
        );
      },
    );
  }
}

Widget _telaCarregando(BuildContext context) {
  return Scaffold(
    backgroundColor: TemaServico.fundo,
    body: Center(child: CircularProgressIndicator(color: Theme.of(context).colorScheme.primary)),
  );
}

/// Primeira coisa que roda ao abrir o app: checa se existe uma atualização
/// obrigatória (ver backend/versao.py) antes de decidir entre login/chat —
/// uma versão muito antiga nem chega a mostrar o resto do app.
class _PortaEntrada extends StatelessWidget {
  final ApiCliente api;
  const _PortaEntrada({required this.api});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: Atualizador.precisaAtualizar(),
      builder: (context, snapshotAtualizacao) {
        if (!snapshotAtualizacao.hasData) return _telaCarregando(context);
        if (snapshotAtualizacao.data == true) return const AtualizacaoTela();
        return _TelaInicial(api: api);
      },
    );
  }
}

/// Decide entre a tela de chat (já tem sessão salva) e a de login, checando
/// o token guardado localmente (SharedPreferences) — evita pedir login toda
/// vez que o app abre.
class _TelaInicial extends StatelessWidget {
  final ApiCliente api;
  const _TelaInicial({required this.api});

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<bool>(
      future: api.temSessaoSalva(),
      builder: (context, snapshot) {
        if (!snapshot.hasData) return _telaCarregando(context);
        return snapshot.data! ? ChatTela(api: api) : LoginTela(api: api);
      },
    );
  }
}
