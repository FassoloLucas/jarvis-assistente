import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:open_filex/open_filex.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';

import 'api.dart';

/// Checa/baixa/instala atualizações do app — necessário porque ele não está
/// na Play Store (não tem update automático de loja nenhuma). O Android
/// sempre vai pedir uma confirmação de instalação no final (trava de
/// segurança do sistema pra apps fora de loja, não dá pra pular) — mas até
/// lá, o fluxo é: checar versão → baixar → abrir o instalador, tudo dentro
/// do app.
class Atualizador {
  /// Compara a versão instalada com a mínima exigida pelo backend
  /// (`GET /versao`, ver backend/versao.py). Se a checagem falhar por
  /// qualquer motivo (sem internet, backend fora do ar), devolve false —
  /// não bloqueia o uso do app por causa de um problema de rede passageiro.
  static Future<bool> precisaAtualizar() async {
    try {
      final info = await PackageInfo.fromPlatform();
      final resposta = await http.get(Uri.parse('${ApiCliente.baseUrl}/versao')).timeout(const Duration(seconds: 8));
      if (resposta.statusCode != 200) return false;
      final corpo = jsonDecode(utf8.decode(resposta.bodyBytes));
      final minima = corpo['versao_minima'] as String;
      return _comparar(info.version, minima) < 0;
    } catch (_) {
      return false;
    }
  }

  /// Compara duas versões "x.y.z". Negativo se `a` for mais antiga que `b`.
  static int _comparar(String a, String b) {
    final partesA = a.split('.').map((p) => int.tryParse(p) ?? 0).toList();
    final partesB = b.split('.').map((p) => int.tryParse(p) ?? 0).toList();
    for (var i = 0; i < 3; i++) {
      final va = i < partesA.length ? partesA[i] : 0;
      final vb = i < partesB.length ? partesB[i] : 0;
      if (va != vb) return va - vb;
    }
    return 0;
  }

  /// Baixa o APK mais recente pra uma pasta temporária, reportando o
  /// progresso (0.0 a 1.0) via `aoProgredir`. Devolve o caminho do arquivo.
  static Future<String> baixarApk({required void Function(double) aoProgredir}) async {
    final requisicao = http.Request('GET', Uri.parse('${ApiCliente.baseUrl}/apk/latest'));
    final resposta = await http.Client().send(requisicao);
    if (resposta.statusCode != 200) {
      throw Exception('Não consegui baixar a atualização (status ${resposta.statusCode}).');
    }

    final tamanhoTotal = resposta.contentLength ?? 0;
    final diretorio = await getTemporaryDirectory();
    final arquivo = File('${diretorio.path}/jarvis_atualizacao.apk');
    final saida = arquivo.openWrite();

    var recebido = 0;
    await for (final pedaco in resposta.stream) {
      saida.add(pedaco);
      recebido += pedaco.length;
      if (tamanhoTotal > 0) aoProgredir(recebido / tamanhoTotal);
    }
    await saida.close();
    return arquivo.path;
  }

  /// Abre o instalador nativo do Android pro APK baixado — o usuário ainda
  /// precisa confirmar ali (não dá pra instalar sem esse toque, é o
  /// Android que exige isso pra apps fora de loja).
  static Future<void> instalar(String caminhoApk) async {
    final resultado = await OpenFilex.open(caminhoApk);
    if (resultado.type != ResultType.done) {
      throw Exception(resultado.message);
    }
  }
}
