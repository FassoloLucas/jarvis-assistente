import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Cor de destaque escolhida pelo usuário (chat, botões, ícones) — o resto
/// do app lê isso via `Theme.of(context).colorScheme.primary`, nunca uma
/// cor fixa direto no widget. Assim, trocar a cor aqui já reflete em todo
/// canto que usa o tema, sem precisar caçar cada widget individualmente.
class TemaServico {
  TemaServico._();

  static const Color fundo = Color(0xFF05090C);

  static const List<(String, Color)> coresDisponiveis = [
    ('Ciano', Color(0xFF00F0FF)),
    ('Roxo', Color(0xFF7C4DFF)),
    ('Verde', Color(0xFF00E676)),
    ('Rosa', Color(0xFFFF4081)),
    ('Âmbar', Color(0xFFFFAB00)),
    ('Vermelho', Color(0xFFFF5252)),
  ];

  static final ValueNotifier<Color> corDestaque = ValueNotifier(coresDisponiveis.first.$2);

  static Future<void> carregar() async {
    final prefs = await SharedPreferences.getInstance();
    final valorSalvo = prefs.getInt('cor_destaque');
    if (valorSalvo != null) {
      corDestaque.value = Color(valorSalvo);
    }
  }

  static Future<void> definirCor(Color cor) async {
    corDestaque.value = cor;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt('cor_destaque', cor.toARGB32());
  }

  static ThemeData montarTema(Color destaque) {
    return ThemeData.dark(useMaterial3: true).copyWith(
      scaffoldBackgroundColor: fundo,
      colorScheme: ColorScheme.fromSeed(
        seedColor: destaque,
        brightness: Brightness.dark,
      ).copyWith(primary: destaque, surface: fundo),
      textSelectionTheme: TextSelectionThemeData(cursorColor: destaque, selectionHandleColor: destaque),
    );
  }
}
