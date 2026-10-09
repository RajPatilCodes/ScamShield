import 'dart:convert';
import 'dart:async';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mime/mime.dart';
import '../models/scan_result.dart';
import '../models/privacy.dart';
import 'session_controller.dart';
import 'session_store.dart';
import 'privacy_service.dart';
import 'privacy_store.dart';
import 'private_artifacts.dart';

class ApiService {
  ApiService({http.Client? client, SessionStore? sessionStore, PrivacyStore? privacyStore, PrivateArtifacts? privateArtifacts, String apiUrl = baseUrl}) : _client = client ?? http.Client(), _baseUrl = apiUrl {
    sessions = SessionController(client: _client, store: sessionStore ?? SessionStore(), apiUrl: apiUrl);
    privacy = PrivacyService(client: _client, sessions: sessions, apiUrl: apiUrl, authenticated: _authenticated,
      store: privacyStore, artifacts: privateArtifacts);
  }
  final http.Client _client;
  final String _baseUrl;
  late final SessionController sessions;
  late final PrivacyService privacy;
  static const baseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');

  Future<bool> isSignedIn() async {
    return sessions.isAuthenticated;
  }
  Future<bool> restoreSession() => sessions.restore();
  Future<void> signOut() async {
    try {
      await sessions.logout();
    } catch (_) {
      // Central state is already signed out; the visible notice and protected
      // pending credential retain truthful server-revocation status for retry.
    }
  }
  Future<Map<String, String>> _headers() async {
    return {'Authorization': 'Bearer ${await sessions.accessToken()}'};
  }
  Future<http.Response> _authenticated(Future<http.Response> Function(Map<String, String>) send) async {
    final generation = sessions.generation;
    final sessionId = sessions.session?.sessionId;
    void ensureCurrent() {
      if (!sessions.isAuthenticated || sessions.generation != generation || sessions.session?.sessionId != sessionId) {
        throw const MediaScanException('Please sign in again.');
      }
    }
    await privacy.artifacts.ready;
    ensureCurrent();
    final original = await _headers();
    ensureCurrent();
    var response = await send(original);
    ensureCurrent();
    if (response.statusCode == 401) {
      if (original['Authorization'] == 'Bearer ${sessions.session?.accessToken}') await sessions.refresh();
      ensureCurrent();
      final refreshed = await _headers();
      ensureCurrent();
      response = await send(refreshed);
      ensureCurrent();
      if (response.statusCode == 401) await sessions.invalidate();
    }
    if (response.statusCode != 401 && (sessions.generation != generation || sessions.session?.sessionId != sessionId)) throw const MediaScanException('Please sign in again.');
    return response;
  }
  void _check(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) return;
    throw MediaScanException(switch (response.statusCode) {
      401 => 'Authentication failed. Check your credentials or sign in again.',
      409 => 'This email is already registered. Sign in instead.',
      413 => 'Choose a file no larger than 20 MiB.',
      415 => 'This media format is not supported. Try JPEG, PNG, or MP4.',
      422 => 'The service rejected the input. Check your email, password, or scan content.',
      _ => 'The service could not complete the request (HTTP ${response.statusCode}).',
    });
  }
  Future<T> _request<T>(Future<T> Function() operation) async {
    try {
      return await operation().timeout(const Duration(seconds: 90));
    } on TimeoutException {
      throw const MediaScanException('The request timed out. Check your connection and try again.');
    } on http.ClientException {
      throw const MediaScanException('Cannot reach the service. Check your connection and API address.');
    } on FormatException {
      throw const MediaScanException('The service returned an invalid response.');
    } on TypeError {
      throw const MediaScanException('The service returned an unexpected response.');
    } on SessionException catch (error) {
      throw MediaScanException(error.message);
    } on PrivacyException catch (error) {
      throw MediaScanException(error.message);
    }
  }
  Future<bool> authenticate(String email, String password, {bool register = false}) => _request(() async {
    if (register) {
      await sessions.store.removeLegacyToken();
      await sessions.post('register', {'email': email.trim(), 'password': password});
      return false;
    }
    await sessions.login(email, password);
    return true;
  });
  Future<void> requestVerification(String email) => _request(() async {
    await sessions.post('verification/request', {'email': email.trim()});
  });
  Future<void> verifyEmail(String token) => _request(() async {
    await sessions.post('verification/confirm', {'token': token.trim()});
  });
  Future<void> requestRecovery(String email) => _request(() async {
    await sessions.post('recovery/request', {'email': email.trim()});
  });
  Future<void> recoverPassword(String token, String password) => _request(() async {
    await sessions.post('recovery/confirm', {'token': token.trim(), 'password': password});
    await sessions.invalidate();
  });
  Future<ScanResult> scan(String content, {bool save = false}) => _request(() async {
    if (save) return privacy.saveScan(content);
    final response = await _authenticated((headers) => _client.post(Uri.parse('$_baseUrl/analysis/analyze'), headers: {...headers, 'Content-Type': 'application/json'}, body: jsonEncode({'content': content})));
    _check(response);
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return ScanResult(score: body['score'] as int, level: body['verdict'] as String, reasons: List<String>.from(body['flags'] as List), actions: const ['Do not share passwords or verification codes', 'Verify the sender using a trusted channel'], content: content, createdAt: DateTime.now());
  });
  Future<List<ScanResult>> history() => _request(() async {
    final response = await _authenticated((headers) => _client.get(Uri.parse('$_baseUrl/analysis/history?page_size=100'), headers: headers));
    _check(response);
    return ((jsonDecode(response.body) as Map<String, dynamic>)['items'] as List).map((e) => ScanResult.fromJson(e as Map<String, dynamic>)).toList();
  });
  Future<ScanResult> scanMedia(XFile file, {String? filename}) => _request(() async {
    final captured = privacy.context;
    final generation = sessions.generation;
    final sessionId = sessions.session?.sessionId;
    final displayName = filename ?? file.name;
    await privacy.artifacts.checkUse(captured, file.path);
    final length = await file.length();
    if (length > 20 * 1024 * 1024) throw const MediaScanException('Choose a file no larger than 20 MiB.');
    if (length == 0) throw const MediaScanException('This file is empty. Choose another file.');
    if (sessions.generation != generation || sessions.session?.sessionId != sessionId) throw const MediaScanException('Please sign in again.');
    final response = await _authenticated((headers) async {
      await privacy.artifacts.checkUse(captured, file.path);
      final request = http.MultipartRequest('POST', Uri.parse('$_baseUrl/analysis/media'));
      request.headers.addAll(headers);
      request.files.add(http.MultipartFile('file', privacy.artifacts.checkedRead(captured, file.path, file.openRead()), length,
        filename: displayName, contentType: MediaType.parse(lookupMimeType(displayName) ?? 'application/octet-stream')));
      return http.Response.fromStream(await _client.send(request));
    });
    _check(response);
    return ScanResult.fromMediaJson(jsonDecode(response.body) as Map<String, dynamic>);
  });
}

class MediaScanException implements Exception {
  const MediaScanException(this.message);
  final String message;
}
