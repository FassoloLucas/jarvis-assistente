import 'package:flutter/material.dart';
import '../servicos/tema.dart';

class PersonalizacaoTela extends StatelessWidget {
  const PersonalizacaoTela({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: TemaServico.fundo,
      appBar: AppBar(
        backgroundColor: TemaServico.fundo,
        title: const Text('Personalização'),
      ),
      body: ValueListenableBuilder<Color>(
        valueListenable: TemaServico.corDestaque,
        builder: (context, corAtual, _) {
          return ListView(
            padding: const EdgeInsets.all(20),
            children: [
              const Text(
                'Cor de destaque',
                style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 6),
              const Text(
                'Usada no chat, botões e ícones do app.',
                style: TextStyle(color: Colors.white54, fontSize: 13),
              ),
              const SizedBox(height: 20),
              Wrap(
                spacing: 16,
                runSpacing: 16,
                children: [
                  for (final (nome, cor) in TemaServico.coresDisponiveis)
                    _AmostraCor(
                      nome: nome,
                      cor: cor,
                      selecionada: cor.toARGB32() == corAtual.toARGB32(),
                      onTap: () => TemaServico.definirCor(cor),
                    ),
                ],
              ),
              const SizedBox(height: 32),
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.05),
                  borderRadius: BorderRadius.circular(16),
                  border: Border.all(color: Colors.white12),
                ),
                child: Row(
                  children: [
                    CircleAvatar(radius: 18, backgroundColor: corAtual, child: const Icon(Icons.smart_toy, size: 18, color: Colors.black)),
                    const SizedBox(width: 12),
                    const Expanded(
                      child: Text(
                        'Prévia: assim ficam as mensagens do Jarvis e os botões no chat.',
                        style: TextStyle(color: Colors.white70, fontSize: 13),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}

class _AmostraCor extends StatelessWidget {
  final String nome;
  final Color cor;
  final bool selecionada;
  final VoidCallback onTap;

  const _AmostraCor({required this.nome, required this.cor, required this.selecionada, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 150),
            width: 52,
            height: 52,
            decoration: BoxDecoration(
              color: cor,
              shape: BoxShape.circle,
              border: Border.all(color: selecionada ? Colors.white : Colors.transparent, width: 3),
              boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.5), blurRadius: selecionada ? 14 : 0, spreadRadius: 1)],
            ),
            child: selecionada ? const Icon(Icons.check, color: Colors.black) : null,
          ),
          const SizedBox(height: 6),
          Text(nome, style: const TextStyle(color: Colors.white70, fontSize: 12)),
        ],
      ),
    );
  }
}
