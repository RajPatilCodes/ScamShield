import 'dart:async';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:image_picker/image_picker.dart';
import 'dart:typed_data';
import 'dart:convert';
import 'dart:io';
import 'package:scamshield_mobile/services/api_service.dart';
import 'package:scamshield_mobile/models/scan_result.dart';
import 'package:scamshield_mobile/models/privacy.dart';
import 'package:scamshield_mobile/services/private_artifacts.dart';
import 'package:scamshield_mobile/services/session_store.dart';
import 'session_store_test.dart' show MemoryCredentials;
import 'privacy_fixtures.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));
  for (final outcome in ['success', 'timeout', 'client-error']) {
    test('late Account A deletion $outcome preserves Account B credentials', () async {
      final gate = Completer<http.Response>();
      final started = Completer<void>();
      var logins = 0;
      final memory = MemoryCredentials();
      final api = privacyApi(MockClient((request) async {
        if (request.url.path.endsWith('/login')) return jsonResponse(privacySession(owner: '${++logins}'));
        if (request.url.path.endsWith('/logout')) return http.Response('', 204);
        started.complete();
        return gate.future;
      }), storage: memory);
      await api.authenticate('a@example.com', 'password123');
      final pending = api.privacy.deleteAccount('a-grant');
      final expectation = expectLater(pending, throwsA(anything));
      await started.future;
      await api.signOut();
      await api.authenticate('b@example.com', 'password123');
      final credentials = Map<String, String>.from(memory.values);
      final generation = api.sessions.generation;
      switch (outcome) {
        case 'success': gate.complete(jsonResponse({'id': 'a-job', 'kind': 'deletion', 'state': 'queued'}, 202));
        case 'timeout': gate.completeError(TimeoutException('synthetic late timeout'));
        case 'client-error': gate.completeError(http.ClientException('synthetic late transport failure'));
      }
      await expectation;
      expect(api.sessions.isAuthenticated, true);
      expect(api.sessions.session!.ownerId, '2');
      expect(api.sessions.generation, generation);
      expect(memory.values, credentials);
    });
  }
  test('missing saved identity never looks up or deletes a replacement integer ID', () async {
    var requests = 0;
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      requests++;
      throw StateError('must not resolve stale ID');
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    final stale = ScanResult.fromJson({'id': 7, 'content': 'old record', 'score': 0, 'verdict': 'low-risk'});
    await expectLater(api.privacy.deleteOne(stale), throwsA(isA<PrivacyException>()));
    expect(requests, 0);
  });
  test('stale keyed result sends only its original key and never substitutes a replacement', () async {
    var requests = 0;
    const originalKey = '00000000-0000-4000-8000-000000000007';
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      requests++;
      expect(request.method, 'DELETE');
      expect(jsonDecode(request.body), {'record_key': originalKey});
      return http.Response('{}', 404);
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    final stale = ScanResult.fromJson({'id': 7, 'record_key': originalKey, 'content': 'old record', 'score': 0, 'verdict': 'low-risk'});
    await expectLater(api.privacy.deleteOne(stale), throwsA(isA<PrivacyException>()));
    expect(requests, 1);
  });
  test('expired selected picker cannot upload even without cleanup running', () async {
    final temp = await Directory.systemTemp.createTemp('phase3-upload-');
    var now = DateTime.utc(2030);
    var uploads = 0;
    final memory = MemoryCredentials();
    final artifacts = PrivateArtifacts(temporaryDirectory: () async => temp, now: () => now);
    final api = ApiService(apiUrl: 'https://api.invalid', sessionStore: SessionStore(storage: memory), privateArtifacts: artifacts,
      client: MockClient((request) async {
        if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
        uploads++;
        throw StateError('expired source must not upload');
      }));
    try {
      await api.authenticate('synthetic@example.com', 'password123');
      final source = File('${temp.path}${Platform.pathSeparator}picker.png');
      await source.writeAsBytes([1, 2, 3]);
      final copy = await artifacts.adoptPickerCopy(api.privacy.context, source.path);
      now = now.add(const Duration(hours: 24));
      expect(await copy.exists(), true);
      await expectLater(api.scanMedia(XFile(copy.path), filename: 'picker.png'), throwsA(isA<MediaScanException>()));
      expect(uploads, 0);
    } finally { await temp.delete(recursive: true); }
  });
  test('late private response cannot cross logout and same-SID rapid login', () async {
    final gate = Completer<http.Response>();
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      if (request.url.path.endsWith('/logout')) return http.Response('', 204);
      return gate.future;
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    final pending = api.privacy.settings();
    final expectation = expectLater(pending, throwsA(isA<MediaScanException>()));
    await Future<void>.delayed(Duration.zero);
    await api.signOut();
    await api.authenticate('synthetic@example.com', 'password123');
    gate.complete(jsonResponse(privacySettings()));
    await expectation;
  });
  test('401 response from an old generation never retries under another account', () async {
    final gate = Completer<http.Response>();
    var privateRequests = 0;
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      if (request.url.path.endsWith('/logout')) return http.Response('', 204);
      privateRequests++;
      return gate.future;
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    final pending = api.history();
    final expectation = expectLater(pending, throwsA(isA<MediaScanException>()));
    await Future<void>.delayed(Duration.zero);
    await api.signOut();
    await api.authenticate('synthetic@example.com', 'password123');
    gate.complete(http.Response('{}', 401));
    await expectation;
    expect(privateRequests, 1);
  });
  test('recent-auth request contains action/target but never refresh credentials', () async {
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      expect(request.followRedirects, false);
      expect(request.body, contains('export_download'));
      expect(request.body, isNot(contains('refresh_token')));
      return jsonResponse({'grant': 'one-time', 'expires_at': 2000000000});
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    expect(await api.privacy.reauthenticate('password123', 'export_download', target: 'job'), 'one-time');
  });
  test('owned picker copy preserves original media filename and MIME semantics', () async {
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      expect(request.url.path, '/analysis/media');
      expect(request.body, contains('filename="invoice.exe.png"'));
      expect(request.body, contains('image/png'));
      return jsonResponse({'filename': 'invoice.exe.png', 'content_type': 'image/png', 'size_bytes': 3,
        'sha256': 'a' * 64, 'verdict': 'review', 'flags': <String>[], 'actions': <String>[], 'malware_scanned': false});
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    final copy = XFile.fromData(Uint8List.fromList([1, 2, 3]), path: 'owned-temporary.picker');
    final result = await api.scanMedia(copy, filename: 'invoice.exe.png');
    expect(result.content, 'invoice.exe.png');
    expect(result.isMedia, true);
  });
  test('logout before headers resolve cannot submit an old scan under a new session', () async {
    var privateRequests = 0;
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      if (request.url.path.endsWith('/logout')) return http.Response('', 204);
      privateRequests++;
      return jsonResponse({'score': 0, 'verdict': 'low-risk', 'flags': <String>[]});
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    final pending = api.scan('old account content');
    final expectation = expectLater(pending, throwsA(isA<MediaScanException>()));
    await api.signOut();
    await api.authenticate('synthetic@example.com', 'password123');
    await expectation;
    expect(privateRequests, 0);
  });
  test('uncertain explicit-save response keeps its idempotency key for retry', () async {
    final keys = <String>[];
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      keys.add(request.headers['Idempotency-Key']!);
      if (keys.length == 1) throw http.ClientException('synthetic response lost after commit');
      return jsonResponse({'id': 7, 'content': 'synthetic text', 'score': 0, 'verdict': 'low-risk', 'flags': <String>[]}, 201);
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    await expectLater(api.scan('synthetic text', save: true), throwsA(isA<MediaScanException>()));
    expect((await api.scan('synthetic text', save: true)).savedId, 7);
    expect(keys.first, keys.last);
  });
}
