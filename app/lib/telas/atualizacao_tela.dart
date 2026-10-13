import 'package:flutter/material.dart';
import '../servicos/atualizador.dart';
import '../servicos/tema.dart';

/// Tela de atualização obrigatória — sem botão de voltar/fechar de
/// propósito (`PopScope(canPop: false)`), o app não segue enquanto a
/// pessoa não atualizar.
class AtualizacaoTela extends StatefulWidget {
  const AtualizacaoTela({super.key});

  @override
  State<AtualizacaoTela> createState() => _AtualizacaoTelaState();
}

class _AtualizacaoTelaState extends State<AtualizacaoTela> {
  bool _baixando = false;
  double _progresso = 0;
  String? _erro;

  Future<void> _atualizar() async {
    setState(() {
      _baixando = true;
      _erro = null;
      _progresso = 0;
    });
    try {
      final caminho = await Atualizador.baixarApk(
        aoProgredir: (p) {
          if (mounted) setState(() => _progresso = p);
        },
      );
      await Atualizador.instalar(caminho);
    } catch (e) {
      if (mounted) setState(() => _erro = '$e');
    } finally {
      if (mounted) setState(() => _baixando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: TemaServico.fundo,
        body: SafeArea(
          child: Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.system_update_alt, size: 64, color: TemaServico.corDestaque.value),
                  const SizedBox(height: 24),
                  const Text(
                    'Atualização obrigatória',
                    style: TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    'Uma nova versão do Jarvis está disponível. Atualize pra continuar usando o app.',
                    style: TextStyle(color: Colors.white70, height: 1.4),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 32),
                  if (_baixando) ...[
                    LinearProgressIndicator(
                      value: _progresso > 0 ? _progresso : null,
                      color: TemaServico.corDestaque.value,
                      backgroundColor: Colors.white10,
                    ),
                    const SizedBox(height: 8),
                    Text('${(_progresso * 100).toStringAsFixed(0)}%', style: const TextStyle(color: Colors.white54)),
                  ] else
                    SizedBox(
                      width: double.infinity,
                      child: ElevatedButton(
                        onPressed: _atualizar,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: TemaServico.corDestaque.value,
                          foregroundColor: Colors.black,
                          padding: const EdgeInsets.symmetric(vertical: 16),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        child: const Text('Atualizar agora'),
                      ),
                    ),
                  if (_erro != null) ...[
                    const SizedBox(height: 16),
                    Text('Erro: $_erro', style: const TextStyle(color: Colors.redAccent), textAlign: TextAlign.center),
                    const SizedBox(height: 8),
                    TextButton(onPressed: _atualizar, child: const Text('Tentar de novo')),
                  ],
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
