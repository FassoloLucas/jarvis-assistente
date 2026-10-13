// Smoke test básico: confirma que o app sobe sem quebrar e mostra a tela
// de login (sem sessão salva, é a primeira coisa que aparece depois da
// checagem de atualização obrigatória).

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:jarvis_app/main.dart';

void main() {
  testWidgets('App sobe e mostra a tela de login', (WidgetTester tester) async {
    // Sem isso, SharedPreferences.getInstance() fica pendurado esperando o
    // plugin nativo (que não existe no ambiente de teste, só num
    // device/emulador de verdade).
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(const JarvisApp());

    // O app faz uma chamada de rede de verdade (checagem de atualização,
    // ver Atualizador.precisaAtualizar) antes de decidir a tela inicial —
    // isso usa Future/Timer reais, que o relógio falso do pumpAndSettle não
    // consegue avançar sozinho (trava em "pumpAndSettle timed out"). Dentro
    // de runAsync, o código roda no event loop de verdade.
    await tester.runAsync(() => Future.delayed(const Duration(seconds: 3)));
    // Duas telas de carregamento em sequência (checagem de atualização, depois
    // checagem de sessão salva) — um pump() só resolve a primeira.
    await tester.pump();
    await tester.pump();

    expect(find.text('J.A.R.V.I.S.'), findsOneWidget);
    expect(find.text('Entrar'), findsWidgets);
  });
}
