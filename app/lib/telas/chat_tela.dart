import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:speech_to_text/speech_to_text.dart' as stt;
import '../servicos/api.dart';
import '../servicos/tema.dart';
import 'historico_drawer.dart';
import 'login_tela.dart';
import 'personalizacao_tela.dart';

class _Mensagem {
  final String texto;
  final bool doUsuario;
  final DateTime hora;
  _Mensagem(this.texto, this.doUsuario) : hora = DateTime.now();
}

class ChatTela extends StatefulWidget {
  final ApiCliente api;
  const ChatTela({super.key, required this.api});

  @override
  State<ChatTela> createState() => _ChatTelaState();
}

class _ChatTelaState extends State<ChatTela> {
  final _controlador = TextEditingController();
  final _rolagem = ScrollController();
  final List<_Mensagem> _mensagens = [];
  final _tocador = AudioPlayer();
  final _reconhecedorVoz = stt.SpeechToText();

  bool _enviando = false;
  bool _ouvindo = false;
  bool _vozDisponivel = false;
  bool _falarRespostas = true;
  String? _conversaIdAtual;
  final _chaveScaffold = GlobalKey<ScaffoldState>();
  // Incrementado a cada "nova conversa"/troca — força o Drawer a recriar
  // seu estado (e recarregar a lista) em vez de reusar o antigo.
  int _versaoDrawer = 0;

  @override
  void initState() {
    super.initState();
    _prepararReconhecimentoVoz();
  }

  Future<void> _prepararReconhecimentoVoz() async {
    // Pede a permissão de microfone (RECORD_AUDIO) na primeira vez que a
    // tela abre — o próprio plugin cuida do popup nativo do Android.
    final disponivel = await _reconhecedorVoz.initialize(
      onError: (erro) => setState(() => _ouvindo = false),
      onStatus: (status) {
        if (status == 'done' || status == 'notListening') {
          setState(() => _ouvindo = false);
        }
      },
    );
    if (mounted) setState(() => _vozDisponivel = disponivel);
  }

  Future<void> _alternarEscuta() async {
    if (_ouvindo) {
      await _reconhecedorVoz.stop();
      setState(() => _ouvindo = false);
      return;
    }
    setState(() => _ouvindo = true);
    await _reconhecedorVoz.listen(
      listenOptions: stt.SpeechListenOptions(localeId: 'pt_BR'),
      onResult: (resultado) {
        _controlador.text = resultado.recognizedWords;
        if (resultado.finalResult && resultado.recognizedWords.trim().isNotEmpty) {
          _enviar();
        }
      },
    );
  }

  Future<void> _enviar() async {
    final texto = _controlador.text.trim();
    if (texto.isEmpty || _enviando) return;

    setState(() {
      _mensagens.add(_Mensagem(texto, true));
      _enviando = true;
      _controlador.clear();
    });
    _rolarParaFinal();

    try {
      final resposta = await widget.api.enviarMensagem(texto, conversaId: _conversaIdAtual);
      final eraConversaNova = _conversaIdAtual == null;
      _conversaIdAtual = resposta.conversaId;
      setState(() => _mensagens.add(_Mensagem(resposta.texto, false)));
      if (_falarRespostas) {
        _tocarEmVozAlta(resposta.texto);
      }
      // Conversa nova acabou de ganhar um título (primeira mensagem) — o
      // Drawer precisa recarregar a lista pra mostrar ela.
      if (eraConversaNova) setState(() => _versaoDrawer++);
    } catch (e) {
      setState(() => _mensagens.add(_Mensagem('Erro: $e', false)));
    } finally {
      setState(() => _enviando = false);
      _rolarParaFinal();
    }
  }

  Future<void> _tocarEmVozAlta(String texto) async {
    try {
      final bytesAudio = await widget.api.gerarFala(texto);
      await _tocador.play(BytesSource(Uint8List.fromList(bytesAudio)));
    } catch (_) {
      // Falha ao gerar/tocar áudio não deve quebrar o chat — a resposta em
      // texto já apareceu na tela, a fala é só um extra.
    }
  }

  void _rolarParaFinal() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_rolagem.hasClients) {
        _rolagem.animateTo(_rolagem.position.maxScrollExtent, duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      }
    });
  }

  Future<void> _sair() async {
    await widget.api.sair();
    if (!mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => LoginTela(api: widget.api)));
  }

  /// Se a conversa apagada era a que estava aberta na tela, limpa a
  /// conversa atual (fica como se tivesse acabado de abrir "Nova conversa").
  void _aoConversaApagada(String conversaId) {
    if (conversaId == _conversaIdAtual) {
      setState(() {
        _mensagens.clear();
        _conversaIdAtual = null;
      });
    }
  }

  void _iniciarNovaConversa() {
    Navigator.of(context).pop(); // fecha o Drawer
    setState(() {
      _mensagens.clear();
      _conversaIdAtual = null;
    });
  }

  Future<void> _selecionarConversa(String conversaId) async {
    Navigator.of(context).pop(); // fecha o Drawer
    setState(() => _enviando = true);
    try {
      final historico = await widget.api.carregarConversa(conversaId);
      setState(() {
        _conversaIdAtual = conversaId;
        _mensagens
          ..clear()
          ..addAll(historico.map((m) => _Mensagem(m.content, m.role == 'user')));
      });
      _rolarParaFinal();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Não consegui abrir essa conversa: $e')));
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  String _formatarHora(DateTime hora) {
    return '${hora.hour.toString().padLeft(2, '0')}:${hora.minute.toString().padLeft(2, '0')}';
  }

  @override
  void dispose() {
    _tocador.dispose();
    _reconhecedorVoz.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final destaque = Theme.of(context).colorScheme.primary;

    return Scaffold(
      key: _chaveScaffold,
      backgroundColor: TemaServico.fundo,
      drawer: HistoricoDrawer(
        key: ValueKey(_versaoDrawer),
        api: widget.api,
        conversaIdAtual: _conversaIdAtual,
        aoSelecionar: _selecionarConversa,
        aoNovaConversa: _iniciarNovaConversa,
        aoApagar: _aoConversaApagada,
      ),
      appBar: AppBar(
        backgroundColor: TemaServico.fundo,
        title: Row(
          children: [
            Icon(Icons.smart_toy_outlined, color: destaque, size: 20),
            const SizedBox(width: 8),
            Text('J.A.R.V.I.S.', style: TextStyle(color: destaque, letterSpacing: 2, fontWeight: FontWeight.w600)),
          ],
        ),
        actions: [
          IconButton(
            icon: Icon(_falarRespostas ? Icons.volume_up_outlined : Icons.volume_off_outlined, color: Colors.white54),
            tooltip: _falarRespostas ? 'Falar respostas em voz alta' : 'Respostas silenciosas',
            onPressed: () => setState(() => _falarRespostas = !_falarRespostas),
          ),
          IconButton(
            icon: const Icon(Icons.palette_outlined, color: Colors.white54),
            tooltip: 'Personalização',
            onPressed: () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => const PersonalizacaoTela())),
          ),
          IconButton(icon: const Icon(Icons.logout, color: Colors.white54), onPressed: _sair),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            Expanded(
              child: _mensagens.isEmpty
                  ? _EstadoVazio(destaque: destaque)
                  : ListView.builder(
                      controller: _rolagem,
                      padding: const EdgeInsets.all(16),
                      itemCount: _mensagens.length,
                      itemBuilder: (context, indice) => _BolhaMensagem(
                        mensagem: _mensagens[indice],
                        corDestaque: destaque,
                        formatarHora: _formatarHora,
                      ),
                    ),
            ),
            if (_enviando) LinearProgressIndicator(minHeight: 2, color: destaque, backgroundColor: Colors.white10),
            if (_ouvindo)
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(Icons.graphic_eq, color: destaque, size: 16),
                    const SizedBox(width: 6),
                    Text('Ouvindo...', style: TextStyle(color: destaque)),
                  ],
                ),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
              child: Row(
                children: [
                  if (_vozDisponivel)
                    IconButton(
                      icon: Icon(_ouvindo ? Icons.mic : Icons.mic_none, color: _ouvindo ? Colors.redAccent : destaque),
                      onPressed: _alternarEscuta,
                    ),
                  Expanded(
                    child: TextField(
                      controller: _controlador,
                      style: const TextStyle(color: Colors.white),
                      onSubmitted: (_) => _enviar(),
                      decoration: InputDecoration(
                        hintText: 'Fala com o Jarvis...',
                        hintStyle: const TextStyle(color: Colors.white38),
                        filled: true,
                        fillColor: Colors.white10,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 12),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Container(
                    decoration: BoxDecoration(color: destaque, shape: BoxShape.circle),
                    child: IconButton(
                      icon: const Icon(Icons.arrow_upward, color: Colors.black),
                      onPressed: _enviar,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _EstadoVazio extends StatelessWidget {
  final Color destaque;
  const _EstadoVazio({required this.destaque});

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(Icons.smart_toy_outlined, size: 56, color: destaque.withValues(alpha: 0.6)),
          const SizedBox(height: 16),
          const Text('Como posso ajudar, chefe?', style: TextStyle(color: Colors.white54, fontSize: 15)),
        ],
      ),
    );
  }
}

class _BolhaMensagem extends StatelessWidget {
  final _Mensagem mensagem;
  final Color corDestaque;
  final String Function(DateTime) formatarHora;

  const _BolhaMensagem({required this.mensagem, required this.corDestaque, required this.formatarHora});

  @override
  Widget build(BuildContext context) {
    final doUsuario = mensagem.doUsuario;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: doUsuario ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          if (!doUsuario) ...[
            CircleAvatar(radius: 14, backgroundColor: corDestaque.withValues(alpha: 0.2), child: Icon(Icons.smart_toy, size: 15, color: corDestaque)),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Column(
              crossAxisAlignment: doUsuario ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
                  decoration: BoxDecoration(
                    color: doUsuario ? corDestaque : Colors.white.withValues(alpha: 0.08),
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(16),
                      topRight: const Radius.circular(16),
                      bottomLeft: Radius.circular(doUsuario ? 16 : 4),
                      bottomRight: Radius.circular(doUsuario ? 4 : 16),
                    ),
                  ),
                  child: Text(
                    mensagem.texto,
                    style: TextStyle(color: doUsuario ? Colors.black : Colors.white, height: 1.3),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.only(top: 3, left: 4, right: 4),
                  child: Text(formatarHora(mensagem.hora), style: const TextStyle(color: Colors.white30, fontSize: 10)),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
