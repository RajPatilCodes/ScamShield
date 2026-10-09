import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/privacy.dart';
import '../models/scan_result.dart';
import 'session_controller.dart';
import 'privacy_store.dart';
import 'private_artifacts.dart';

class PrivacyService {
  PrivacyService({required this.client, required this.sessions, required this.apiUrl,
    required this.authenticated, PrivacyStore? store, PrivateArtifacts? artifacts}) :
    store = store ?? PrivacyStore(), artifacts = artifacts ?? PrivateArtifacts() {
    sessions.addListener(_transition);
  }
  final http.Client client;
  final SessionController sessions;
  final String apiUrl;
  final Future<http.Response> Function(Future<http.Response> Function(Map<String, String>)) authenticated;
  final PrivacyStore store;
  final PrivateArtifacts artifacts;
  final ValueNotifier<int> historyRevision = ValueNotifier(0);
  int artifactHours = 24;
  int exportMaxBytes = 100000000;
  String? _lastContext;
  final Map<String, ({String payload, String key})> _pendingMutations = {};
  PrivateContext get context {
    final session = sessions.session;
    if (session == null) throw const PrivacyException('Please sign in again.');
    return PrivateContext(apiUrl, session.ownerId, session.sessionId, sessions.generation);
  }
  void _transition() {
    final next = sessions.isAuthenticated ? context : null;
    if (_lastContext != next?.requestKey) {
      _pendingMutations.clear();
      historyRevision.value++;
    }
    _lastContext = next?.requestKey;
    artifacts.bind(next);
  }
  void check(PrivateContext captured) {
    if (!sessions.isAuthenticated || context.requestKey != captured.requestKey) throw const PrivacyException('Account changed. Please try again.');
  }
  Map<String, dynamic> _body(http.Response response) {
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw PrivacyException(switch (response.statusCode) {
        403 => 'Current consent or recent authentication is required.',
        404 => 'This private object or status is unavailable.',
        409 => 'The operation conflicts with current state. Refresh and try again.',
        410 => 'This export expired or was invalidated.',
        429 => 'Too many privacy requests. Please try again later.',
        _ => 'The privacy service could not complete the request.',
      });
    }
    return jsonDecode(response.body) as Map<String, dynamic>;
  }
  Future<Map<String, dynamic>> _request(String method, String path, {Map<String, dynamic>? body, String? key}) async {
    final captured = context;
    final response = await authenticated((headers) async {
      check(captured);
      final request = http.Request(method, Uri.parse('$apiUrl/v1/privacy$path'))
        ..followRedirects = false
        ..headers.addAll({...headers, 'Content-Type': 'application/json', if (key != null) 'Idempotency-Key': key});
      if (body != null) request.body = jsonEncode(body);
      return http.Response.fromStream(await client.send(request));
    }).timeout(const Duration(seconds: 90));
    check(captured);
    return _body(response);
  }
  Future<Map<String, dynamic>> _mutate(String method, String path, Map<String, dynamic> body) async {
    final captured = context;
    final identity = '$method:$path';
    final payload = jsonEncode({...body}..remove('grant'));
    final previous = _pendingMutations[identity];
    final pending = previous?.payload == payload ? previous! : (payload: payload, key: privateNonce());
    _pendingMutations[identity] = pending;
    // Keep the same key after an uncertain response; do not silently create
    // another saved object/job on the user's explicit retry. Memory only.
    final result = await _request(method, path, key: pending.key, body: body);
    check(captured);
    if (_pendingMutations[identity] == pending) _pendingMutations.remove(identity);
    return result;
  }
  Future<PrivacySettings> settings() async {
    final value = PrivacySettings.fromJson(await _request('GET', ''));
    artifactHours = value.artifactHours;
    exportMaxBytes = value.exportMaxBytes;
    return value;
  }
  Future<void> consent(PrivacySettings settings, bool enabled) async {
    await _mutate('PUT', '/consents/${settings.purpose}', {
      'granted': enabled, 'version': settings.noticeVersion, 'expected_version': settings.preferenceVersion});
  }
  Future<ScanResult> saveScan(String content) async => ScanResult.fromJson(await _mutate('POST', '/analyses',
    {'content': content, 'save': true}));
  Future<ScanResult> detail(int id) async => ScanResult.fromJson(await _request('GET', '/analyses/$id'));
  Future<PrivacyJob> deleteOne(ScanResult result) async {
    if (result.savedId == null || result.recordKey == null || result.recordKey!.isEmpty) {
      throw const PrivacyException('Saved identity is unavailable. Refresh history before deleting.');
    }
    final captured = context;
    final job = PrivacyJob.fromJson(await _mutate('DELETE', '/analyses/${result.savedId}', {'record_key': result.recordKey}));
    check(captured);
    historyRevision.value++;
    return job;
  }
  Future<String> reauthenticate(String password, String action, {String target = 'self'}) async {
    final body = await _request('POST', '/reauthenticate', body: {'password': password, 'action': action, 'target': target});
    return body['grant'] as String;
  }
  Future<PrivacyJob> createExport(String grant) async => PrivacyJob.fromJson(await _mutate('POST', '/exports', {'grant': grant}));
  Future<List<PrivacyJob>> exports() async => ((await _request('GET', '/exports'))['items'] as List)
    .map((item) => PrivacyJob.fromJson(item as Map<String, dynamic>)).toList();
  Future<PrivacyJob> deleteSaved(String grant) async {
    final captured = context;
    // Drop cached identities immediately and fence already-running history reads.
    historyRevision.value++;
    try {
      final job = PrivacyJob.fromJson(await _mutate('POST', '/deletions', {'scope': 'saved', 'grant': grant}));
      check(captured);
      return job;
    } finally {
      if (sessions.isAuthenticated && context.requestKey == captured.requestKey) historyRevision.value++;
    }
  }
  Future<PrivacyJob> deletionStatus(String id) async => PrivacyJob.fromJson(await _request('GET', '/deletions/$id'));
  Future<PrivacyJob> deleteAccount(String grant) async {
    final captured = context;
    final pending = await store.receipt(apiUrl);
    check(captured);
    final sameAccount = pending?['account_key'] == captured.accountKey;
    final receipt = sameAccount ? pending!['receipt'] as String : privateNonce();
    final key = sameAccount ? pending!['request_key'] as String : privateNonce();
    await store.saveReceipt(apiUrl, receipt, key, accountKey: captured.accountKey);
    check(captured);
    try {
      final job = PrivacyJob.fromJson(await _request('POST', '/deletions', key: key,
        body: {'scope': 'account', 'receipt': receipt, 'grant': grant}));
      check(captured);
      await sessions.invalidate();
      return job;
    } on TimeoutException {
      check(captured);
      await sessions.invalidate();
      throw const PrivacyException('Server confirmation is uncertain. Check protected deletion status.');
    } on http.ClientException {
      check(captured);
      await sessions.invalidate();
      throw const PrivacyException('Server confirmation is uncertain. Check protected deletion status.');
    }
  }
  Future<PrivacyJob?> receiptStatus() async {
    final pending = await store.receipt(apiUrl);
    if (pending == null) return null;
    SessionController.validateCredentialUrl(apiUrl);
    final request = http.Request('POST', Uri.parse('$apiUrl/v1/privacy/deletions/status'))
      ..followRedirects = false
      ..headers['Content-Type'] = 'application/json'
      ..body = jsonEncode({'receipt': pending['receipt']});
    return PrivacyJob.fromJson(_body(await client.send(request).then(http.Response.fromStream).timeout(const Duration(seconds: 90))));
  }
  Future<File> download(PrivacyJob job, String grant) async {
    final captured = context;
    artifacts.bind(captured);
    await artifacts.prepare(captured);
    var access = await sessions.accessToken();
    check(captured);
    Future<http.StreamedResponse> send() {
      check(captured);
      final request = http.Request('GET', Uri.parse('$apiUrl/v1/privacy/exports/${job.id}/content'))
        ..followRedirects = false
        ..headers.addAll({'Authorization': 'Bearer $access', 'X-Recent-Auth': grant});
      return client.send(request).timeout(const Duration(seconds: 90));
    }
    var response = await send();
    check(captured);
    if (response.statusCode == 401) {
      await response.stream.drain<void>();
      await sessions.refresh();
      check(captured);
      access = await sessions.accessToken();
      response = await send();
    }
    check(captured);
    if (response.statusCode != 200) {
      await response.stream.drain<void>();
      check(captured);
      if (response.statusCode == 401) await sessions.invalidate();
      throw const PrivacyException('Export unavailable or recent authentication expired.');
    }
    final expected = response.contentLength;
    if (expected == null || expected > exportMaxBytes) {
      await response.stream.drain<void>();
      throw const PrivacyException('Invalid export size.');
    }
    return artifacts.download(captured, response.stream, expected, artifactHours: artifactHours, maxBytes: exportMaxBytes);
  }
}
