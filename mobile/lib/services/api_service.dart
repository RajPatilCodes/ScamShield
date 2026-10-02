import 'dart:convert';
import 'dart:async';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:image_picker/image_picker.dart';
import 'package:mime/mime.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/scan_result.dart';

class ApiService {
  ApiService({http.Client? client}) : _client = client ?? http.Client();
  final http.Client _client;
  static const baseUrl = String.fromEnvironment('API_BASE_URL', defaultValue: 'http://10.0.2.2:8000');

  Future<bool> isSignedIn() async {
    final token = (await SharedPreferences.getInstance()).getString('token');
    return token != null && token.isNotEmpty && token != 'local-session';
  }
  Future<void> signOut() async => (await SharedPreferences.getInstance()).remove('token');
  Future<Map<String, String>> _headers() async {
    if (!await isSignedIn()) throw const MediaScanException('Please sign in again.');
    return {'Authorization': 'Bearer ${(await SharedPreferences.getInstance()).getString('token')}'};
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
    }
  }
  Future<bool> authenticate(String email, String password, {bool register = false}) => _request(() async {
    final response = await _client.post(Uri.parse('$baseUrl/auth/${register ? 'register' : 'login'}'), headers: {'Content-Type': 'application/json'}, body: jsonEncode({'email': email.trim(), 'password': password}));
    _check(response);
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    final token = body['access_token'] as String?;
    if (token == null || token.isEmpty || token == 'local-session') throw const MediaScanException('The service did not return a valid session.');
    await (await SharedPreferences.getInstance()).setString('token', token);
    return true;
  });
  Future<ScanResult> scan(String content) => _request(() async {
    final response = await _client.post(Uri.parse('$baseUrl/analysis/analyze'), headers: {...await _headers(), 'Content-Type': 'application/json'}, body: jsonEncode({'content': content}));
    _check(response);
    final body = jsonDecode(response.body) as Map<String, dynamic>;
    return ScanResult(score: body['score'] as int, level: body['verdict'] as String, reasons: List<String>.from(body['flags'] as List), actions: const ['Do not share passwords or verification codes', 'Verify the sender using a trusted channel'], content: content, createdAt: DateTime.now());
  });
  Future<List<ScanResult>> history() => _request(() async {
    final response = await _client.get(Uri.parse('$baseUrl/analysis/history?page_size=100'), headers: await _headers());
    _check(response);
    return ((jsonDecode(response.body) as Map<String, dynamic>)['items'] as List).map((e) => ScanResult.fromJson(e as Map<String, dynamic>)).toList();
  });
  Future<ScanResult> scanMedia(XFile file) => _request(() async {
    final length = await file.length();
    if (length > 20 * 1024 * 1024) throw const MediaScanException('Choose a file no larger than 20 MiB.');
    if (length == 0) throw const MediaScanException('This file is empty. Choose another file.');
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/analysis/media'));
    request.headers.addAll(await _headers());
    request.files.add(http.MultipartFile('file', file.openRead(), length, filename: file.name, contentType: MediaType.parse(lookupMimeType(file.name) ?? 'application/octet-stream')));
    final response = await http.Response.fromStream(await _client.send(request));
    _check(response);
    return ScanResult.fromMediaJson(jsonDecode(response.body) as Map<String, dynamic>);
  });
}

class MediaScanException implements Exception {
  const MediaScanException(this.message);
  final String message;
}
