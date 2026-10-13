import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

/// Um item da lista de conversas passadas (sem as mensagens em si).
class ResumoConversa {
  final String id;
  final String titulo;
  ResumoConversa({required this.id, required this.titulo});

  factory ResumoConversa.deJson(Map<String, dynamic> json) =>
      ResumoConversa(id: json['id'], titulo: json['titulo']);
}

/// Uma mensagem já trocada, carregada do histórico de uma conversa.
class MensagemHistorico {
  final String role; // "user" ou "assistant"
  final String content;
  MensagemHistorico({required this.role, required this.content});

  factory MensagemHistorico.deJson(Map<String, dynamic> json) =>
      MensagemHistorico(role: json['role'], content: json['content']);
}

/// Resposta de uma mensagem enviada: o texto e o id da conversa (pra
/// continuar mandando mensagens nessa mesma conversa depois).
class RespostaChat {
  final String texto;
  final String conversaId;
  RespostaChat({required this.texto, required this.conversaId});
}

/// Cliente do backend do J.A.R.V.I.S. (ver backend/main.py), hospedado no
/// Render — funciona de qualquer rede, sem precisar do PC ligado nem do
/// túnel USB (que só era usado durante o desenvolvimento local).
class ApiCliente {
  static const String baseUrl = String.fromEnvironment('JARVIS_BACKEND_URL', defaultValue: 'http://127.0.0.1:8000');

  String? _token;

  Future<void> _carregarToken() async {
    if (_token != null) return;
    final prefs = await SharedPreferences.getInstance();
    _token = prefs.getString('token');
  }

  Future<bool> temSessaoSalva() async {
    await _carregarToken();
    return _token != null;
  }

  Future<void> _salvarToken(String token) async {
    _token = token;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('token', token);
  }

  Future<void> sair() async {
    _token = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('token');
  }

  Future<String?> cadastrar(String email, String senha, String nome) async {
    final resposta = await http.post(
      Uri.parse('$baseUrl/cadastro'),
      headers: {'Content-Type': 'application/json; charset=utf-8'},
      body: jsonEncode({'email': email, 'senha': senha, 'nome': nome}),
    );
    if (resposta.statusCode != 200) {
      return _mensagemDeErro(resposta);
    }
    return null; // sem erro
  }

  /// Devolve null em caso de sucesso, ou uma mensagem de erro pra mostrar.
  Future<String?> login(String email, String senha) async {
    final resposta = await http.post(
      Uri.parse('$baseUrl/login'),
      headers: {'Content-Type': 'application/json; charset=utf-8'},
      body: jsonEncode({'email': email, 'senha': senha}),
    );
    if (resposta.statusCode != 200) {
      return _mensagemDeErro(resposta);
    }
    final corpo = jsonDecode(utf8.decode(resposta.bodyBytes));
    await _salvarToken(corpo['token']);
    return null;
  }

  Map<String, String> get _cabecalhoAutenticado => {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': 'Bearer $_token',
      };

  /// Manda uma mensagem. Se `conversaId` for null, o backend cria uma
  /// conversa nova sozinho — o id dela vem na resposta, pra usar nas
  /// próximas mensagens da mesma conversa.
  Future<RespostaChat> enviarMensagem(String mensagem, {String? conversaId}) async {
    await _carregarToken();
    final resposta = await http.post(
      Uri.parse('$baseUrl/chat'),
      headers: _cabecalhoAutenticado,
      body: jsonEncode({'mensagem': mensagem, 'conversa_id': ?conversaId}),
    );
    if (resposta.statusCode != 200) {
      throw Exception(_mensagemDeErro(resposta));
    }
    final corpo = jsonDecode(utf8.decode(resposta.bodyBytes));
    return RespostaChat(texto: corpo['resposta'], conversaId: corpo['conversa_id']);
  }

  Future<List<ResumoConversa>> listarConversas() async {
    await _carregarToken();
    final resposta = await http.get(Uri.parse('$baseUrl/conversas'), headers: _cabecalhoAutenticado);
    if (resposta.statusCode != 200) {
      throw Exception(_mensagemDeErro(resposta));
    }
    final corpo = jsonDecode(utf8.decode(resposta.bodyBytes));
    return (corpo['conversas'] as List).map((c) => ResumoConversa.deJson(c)).toList();
  }

  /// Apaga só o histórico de mensagens dessa conversa — nunca afeta a
  /// memória de longo prazo (fatos aprendidos), que é guardada à parte.
  Future<void> apagarConversa(String conversaId) async {
    await _carregarToken();
    final resposta = await http.delete(Uri.parse('$baseUrl/conversas/$conversaId'), headers: _cabecalhoAutenticado);
    if (resposta.statusCode != 200) {
      throw Exception(_mensagemDeErro(resposta));
    }
  }

  Future<List<MensagemHistorico>> carregarConversa(String conversaId) async {
    await _carregarToken();
    final resposta = await http.get(Uri.parse('$baseUrl/conversas/$conversaId'), headers: _cabecalhoAutenticado);
    if (resposta.statusCode != 200) {
      throw Exception(_mensagemDeErro(resposta));
    }
    final corpo = jsonDecode(utf8.decode(resposta.bodyBytes));
    return (corpo['mensagens'] as List).map((m) => MensagemHistorico.deJson(m)).toList();
  }

  /// Devolve os bytes do mp3 gerado pro texto — mesma voz do desktop
  /// (edge-tts, ver backend/voz.py). Quem chama decide como tocar.
  Future<List<int>> gerarFala(String texto) async {
    await _carregarToken();
    final resposta = await http.post(
      Uri.parse('$baseUrl/falar'),
      headers: _cabecalhoAutenticado,
      body: jsonEncode({'texto': texto}),
    );
    if (resposta.statusCode != 200) {
      throw Exception(_mensagemDeErro(resposta));
    }
    return resposta.bodyBytes;
  }

  String _mensagemDeErro(http.Response resposta) {
    try {
      final corpo = jsonDecode(utf8.decode(resposta.bodyBytes));
      return corpo['detail']?.toString() ?? 'Erro desconhecido (${resposta.statusCode}).';
    } catch (_) {
      return 'Erro desconhecido (${resposta.statusCode}).';
    }
  }
}
