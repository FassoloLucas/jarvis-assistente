import 'package:flutter/material.dart';
import '../servicos/api.dart';
import '../servicos/tema.dart';

/// Aba lateral com o histórico de conversas + botão de nova conversa.
class HistoricoDrawer extends StatefulWidget {
  final ApiCliente api;
  final String? conversaIdAtual;
  final void Function(String conversaId) aoSelecionar;
  final VoidCallback aoNovaConversa;
  // Chamado depois que uma conversa é apagada de verdade — pra tela de
  // chat limpar a tela se era a conversa aberta no momento.
  final void Function(String conversaId) aoApagar;

  const HistoricoDrawer({
    super.key,
    required this.api,
    required this.conversaIdAtual,
    required this.aoSelecionar,
    required this.aoNovaConversa,
    required this.aoApagar,
  });

  @override
  State<HistoricoDrawer> createState() => _HistoricoDrawerState();
}

class _HistoricoDrawerState extends State<HistoricoDrawer> {
  List<ResumoConversa>? _conversas;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final conversas = await widget.api.listarConversas();
      if (mounted) setState(() => _conversas = conversas);
    } catch (e) {
      if (mounted) setState(() => _erro = '$e');
    }
  }

  Future<bool> _confirmarExclusao(BuildContext context, String titulo) async {
    final confirmou = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF10161B),
        title: const Text('Apagar conversa?', style: TextStyle(color: Colors.white)),
        content: Text(
          '"$titulo" vai ser apagada. Isso não afeta o que o Jarvis já aprendeu e guardou na memória — só o histórico dessa conversa some.',
          style: const TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.of(context).pop(false), child: const Text('Cancelar')),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Apagar', style: TextStyle(color: Colors.redAccent)),
          ),
        ],
      ),
    );
    return confirmou ?? false;
  }

  Future<void> _apagar(ResumoConversa conversa) async {
    try {
      await widget.api.apagarConversa(conversa.id);
      setState(() => _conversas?.removeWhere((c) => c.id == conversa.id));
      widget.aoApagar(conversa.id);
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Não consegui apagar: $e')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final destaque = Theme.of(context).colorScheme.primary;

    return Drawer(
      backgroundColor: TemaServico.fundo,
      child: SafeArea(
        child: Column(
          children: [
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 16, 16, 8),
              child: Row(
                children: [
                  Icon(Icons.smart_toy_outlined, color: Colors.white54, size: 18),
                  SizedBox(width: 8),
                  Text('Conversas', style: TextStyle(color: Colors.white70, fontWeight: FontWeight.w600)),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: SizedBox(
                width: double.infinity,
                child: ElevatedButton.icon(
                  onPressed: widget.aoNovaConversa,
                  icon: const Icon(Icons.add),
                  label: const Text('Nova conversa'),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: destaque,
                    foregroundColor: Colors.black,
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ),
            ),
            const Divider(color: Colors.white12, height: 24),
            Expanded(child: _corpo(destaque)),
          ],
        ),
      ),
    );
  }

  Widget _corpo(Color destaque) {
    if (_erro != null) {
      return Padding(
        padding: const EdgeInsets.all(16),
        child: Text('Não consegui carregar o histórico: $_erro', style: const TextStyle(color: Colors.white38)),
      );
    }
    final conversas = _conversas;
    if (conversas == null) {
      return Center(child: CircularProgressIndicator(color: destaque));
    }
    if (conversas.isEmpty) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: Text('Nenhuma conversa ainda.', style: TextStyle(color: Colors.white38)),
      );
    }
    return ListView.builder(
      itemCount: conversas.length,
      itemBuilder: (context, indice) {
        final conversa = conversas[indice];
        final selecionada = conversa.id == widget.conversaIdAtual;
        return Dismissible(
          key: ValueKey(conversa.id),
          direction: DismissDirection.endToStart,
          confirmDismiss: (_) => _confirmarExclusao(context, conversa.titulo),
          onDismissed: (_) => _apagar(conversa),
          background: Container(
            color: Colors.redAccent.withValues(alpha: 0.25),
            alignment: Alignment.centerRight,
            padding: const EdgeInsets.only(right: 20),
            child: const Icon(Icons.delete_outline, color: Colors.redAccent),
          ),
          child: ListTile(
            selected: selecionada,
            selectedTileColor: destaque.withValues(alpha: 0.12),
            leading: Icon(Icons.chat_bubble_outline, color: selecionada ? destaque : Colors.white38, size: 20),
            title: Text(
              conversa.titulo,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(color: selecionada ? Colors.white : Colors.white70),
            ),
            trailing: IconButton(
              icon: const Icon(Icons.delete_outline, color: Colors.white24, size: 20),
              onPressed: () async {
                if (await _confirmarExclusao(context, conversa.titulo)) {
                  _apagar(conversa);
                }
              },
            ),
            onTap: () => widget.aoSelecionar(conversa.id),
          ),
        );
      },
    );
  }
}
