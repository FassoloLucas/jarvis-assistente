import 'package:flutter/material.dart';
import '../servicos/api.dart';
import '../servicos/tema.dart';
import 'chat_tela.dart';

class LoginTela extends StatefulWidget {
  final ApiCliente api;
  const LoginTela({super.key, required this.api});

  @override
  State<LoginTela> createState() => _LoginTelaState();
}

class _LoginTelaState extends State<LoginTela> with SingleTickerProviderStateMixin {
  final _emailControlador = TextEditingController();
  final _senhaControlador = TextEditingController();
  final _nomeControlador = TextEditingController();
  bool _modoCadastro = false;
  bool _carregando = false;
  String? _erro;

  late final AnimationController _pulso = AnimationController(
    vsync: this,
    duration: const Duration(seconds: 2),
  )..repeat(reverse: true);

  @override
  void dispose() {
    _pulso.dispose();
    super.dispose();
  }

  Future<void> _enviar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });

    String? erro;
    if (_modoCadastro) {
      erro = await widget.api.cadastrar(
        _emailControlador.text.trim(),
        _senhaControlador.text,
        _nomeControlador.text.trim(),
      );
      // Cadastrou com sucesso (erro == null) — loga em seguida, sem pedir
      // de novo. ??= só avalia o login se erro ainda for null.
      erro ??= await widget.api.login(_emailControlador.text.trim(), _senhaControlador.text);
    } else {
      erro = await widget.api.login(_emailControlador.text.trim(), _senhaControlador.text);
    }

    if (!mounted) return;

    if (erro != null) {
      setState(() {
        _carregando = false;
        _erro = erro;
      });
      return;
    }

    Navigator.of(context).pushReplacement(
      MaterialPageRoute(builder: (_) => ChatTela(api: widget.api)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final destaque = Theme.of(context).colorScheme.primary;

    return Scaffold(
      backgroundColor: TemaServico.fundo,
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                // "Respiração" do reator — o brilho pulsa devagar, como se
                // estivesse vivo, em vez de um ícone estático.
                AnimatedBuilder(
                  animation: _pulso,
                  builder: (context, filho) {
                    final intensidade = 0.7 + (_pulso.value * 0.3); // 0.7 a 1.0
                    return Container(
                      width: 84,
                      height: 84,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        gradient: RadialGradient(
                          colors: [destaque.withValues(alpha: 0.25 * intensidade), Colors.transparent],
                        ),
                        border: Border.all(color: destaque.withValues(alpha: 0.6 * intensidade), width: 1.5),
                        boxShadow: [
                          BoxShadow(color: destaque.withValues(alpha: 0.35 * intensidade), blurRadius: 24, spreadRadius: 2),
                        ],
                      ),
                      child: filho,
                    );
                  },
                  child: Icon(Icons.smart_toy_outlined, color: destaque, size: 38),
                ),
                const SizedBox(height: 20),
                Text(
                  'J.A.R.V.I.S.',
                  style: TextStyle(
                    color: destaque,
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                    letterSpacing: 4,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  _modoCadastro ? 'Criar conta' : 'Entrar',
                  style: const TextStyle(color: Colors.white70, fontSize: 16),
                ),
                const SizedBox(height: 32),
                if (_modoCadastro) ...[
                  _campo(_nomeControlador, 'Nome'),
                  const SizedBox(height: 12),
                ],
                _campo(_emailControlador, 'E-mail'),
                const SizedBox(height: 12),
                _campo(_senhaControlador, 'Senha', senha: true),
                if (_erro != null) ...[
                  const SizedBox(height: 16),
                  Text(_erro!, style: const TextStyle(color: Colors.redAccent)),
                ],
                const SizedBox(height: 24),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: _carregando ? null : _enviar,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: destaque,
                      foregroundColor: Colors.black,
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: _carregando
                        ? const SizedBox(
                            width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.black))
                        : Text(_modoCadastro ? 'Criar conta' : 'Entrar'),
                  ),
                ),
                TextButton(
                  onPressed: _carregando ? null : () => setState(() => _modoCadastro = !_modoCadastro),
                  child: Text(
                    _modoCadastro ? 'Já tenho conta — entrar' : 'Não tenho conta — criar',
                    style: const TextStyle(color: Colors.white54),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _campo(TextEditingController controlador, String rotulo, {bool senha = false}) {
    return TextField(
      controller: controlador,
      obscureText: senha,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: rotulo,
        labelStyle: const TextStyle(color: Colors.white54),
        filled: true,
        fillColor: Colors.white10,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
      ),
    );
  }
}
