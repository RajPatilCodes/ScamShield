import 'dart:async';
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:scamshield_mobile/services/session_controller.dart';
import 'package:scamshield_mobile/services/session_store.dart';
import 'session_store_test.dart' show MemoryCredentials;

Map<String, dynamic> syntheticSession({String refresh = 'synthetic-refresh', int? expires}) {
  const sid = '00000000-0000-4000-8000-000000000001';
  final payload = base64Url.encode(utf8.encode(jsonEncode({'sub': '1', 'sid': sid, 'purpose': 'access',
    'exp': expires ?? DateTime.now().add(const Duration(minutes: 10)).millisecondsSinceEpoch ~/ 1000}))).replaceAll('=', '');
  return {'access_token': 'synthetic.$payload.signature', 'refresh_token': refresh,
    'session_id': sid, 'token_type': 'bearer', 'expires_in': 600};
}
http.Response sessionResponse({String refresh = 'synthetic-refresh'}) => http.Response(jsonEncode(syntheticSession(refresh: refresh)), 200);

class UnavailableCredentials extends MemoryCredentials {
  @override Future<void> write(String key, String value) async => throw StateError('synthetic storage unavailable');
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));
  test('restoration rotates stored refresh; access remains memory only', () async {
    final memory = MemoryCredentials();
    final store = SessionStore(storage: memory);
    await store.write(const StoredSession(refreshToken: 'old-refresh', apiUrl: 'https://api.invalid'));
    final controller = SessionController(store: store, apiUrl: 'https://api.invalid', client: MockClient((request) async {
      expect(request.url.path, '/v1/auth/refresh');
      expect(jsonDecode(request.body), {'refresh_token': 'old-refresh'});
      return sessionResponse(refresh: 'successor');
    }));
    expect(await controller.restore(), true);
    expect((await store.read())!.refreshToken, 'successor');
    expect(memory.values.values.single, isNot(contains('access_token')));
  });
  test('concurrent refresh calls share exactly one rotation', () async {
    final store = SessionStore(storage: MemoryCredentials());
    await store.write(const StoredSession(refreshToken: 'old', apiUrl: 'https://api.invalid'));
    var calls = 0;
    final gate = Completer<http.Response>();
    final controller = SessionController(store: store, apiUrl: 'https://api.invalid', client: MockClient((_) async { calls++; return gate.future; }));
    final first = controller.refresh();
    final second = controller.refresh();
    gate.complete(sessionResponse());
    await Future.wait([first, second]);
    expect(calls, 1);
  });
  test('revoked refresh clears credentials and authenticated state', () async {
    final store = SessionStore(storage: MemoryCredentials());
    await store.write(const StoredSession(refreshToken: 'revoked', apiUrl: 'https://api.invalid'));
    final controller = SessionController(store: store, apiUrl: 'https://api.invalid', client: MockClient((_) async => http.Response('{}', 401)));
    expect(await controller.restore(), false);
    expect(controller.isAuthenticated, false);
    expect(await store.read(), null);
  });
  test('uncertain refresh is not retried; it becomes pending revocation', () async {
    final store = SessionStore(storage: MemoryCredentials());
    await store.write(const StoredSession(refreshToken: 'uncertain', apiUrl: 'https://api.invalid'));
    final controller = SessionController(store: store, apiUrl: 'https://api.invalid', client: MockClient((_) async => throw http.ClientException('offline')));
    expect(await controller.restore(), false);
    expect((await store.read())!.pendingLogout, true);
  });
  test('logout calls server and clears protected credentials', () async {
    final store = SessionStore(storage: MemoryCredentials());
    final paths = <String>[];
    final controller = SessionController(store: store, apiUrl: 'https://api.invalid', client: MockClient((request) async {
      paths.add(request.url.path);
      return request.url.path.endsWith('logout') ? http.Response('', 204) : sessionResponse();
    }));
    await controller.login('synthetic@example.com', 'synthetic-password');
    await controller.logout();
    expect(paths, ['/v1/auth/login', '/v1/auth/logout']);
    expect(controller.isAuthenticated, false);
    expect(await store.read(), null);
  });
  test('failed logout keeps only pending revocation and retries it on startup', () async {
    final store = SessionStore(storage: MemoryCredentials());
    var offline = false;
    final paths = <String>[];
    final client = MockClient((request) async {
      paths.add(request.url.path);
      if (offline) throw http.ClientException('offline');
      return request.url.path.endsWith('logout') ? http.Response('', 204) : sessionResponse();
    });
    final controller = SessionController(store: store, apiUrl: 'https://api.invalid', client: client);
    await controller.login('synthetic@example.com', 'synthetic-password');
    offline = true;
    await expectLater(controller.logout(), throwsA(isA<SessionException>()));
    expect(controller.isAuthenticated, false);
    expect((await store.read())!.pendingLogout, true);
    offline = false;
    paths.clear();
    expect(await SessionController(store: store, apiUrl: 'https://api.invalid', client: client).restore(), false);
    expect(paths, ['/v1/auth/logout']);
    expect(await store.read(), null);
  });
  test('logout during login revokes late credentials without resurrection', () async {
    final store = SessionStore(storage: MemoryCredentials());
    final gate = Completer<http.Response>();
    final started = Completer<void>();
    final controller = SessionController(store: store, apiUrl: 'https://api.invalid', client: MockClient((request) async {
      if (request.url.path.endsWith('login')) { started.complete(); return gate.future; }
      expect(request.url.path, '/v1/auth/logout');
      return http.Response('', 204);
    }));
    final login = controller.login('synthetic@example.com', 'synthetic-password');
    await started.future;
    final logout = controller.logout();
    gate.complete(sessionResponse());
    await Future.wait([login, logout]);
    expect(controller.isAuthenticated, false);
    expect(await store.read(), null);
  });
  test('only the approved debug address permits HTTP', () {
    SessionController.validateCredentialUrl('http://10.0.2.2:8000', debug: true);
    for (final url in ['http://10.0.2.2:8000', 'http://192.168.1.3:8000', 'http://localhost:8000', 'https://user:pass@api.invalid', 'https://']) {
      expect(() => SessionController.validateCredentialUrl(url, debug: false), throwsA(isA<SessionException>()));
    }
    expect(() => SessionController.validateCredentialUrl('http://192.168.1.3:8000', debug: true), throwsA(isA<SessionException>()));
    SessionController.validateCredentialUrl('https://api.invalid', debug: false);
  });
  test('expired in-memory access is refreshed before use', () async {
    var now = DateTime.now();
    var rotations = 0;
    final store = SessionStore(storage: MemoryCredentials());
    final controller = SessionController(store: store, apiUrl: 'https://api.invalid', now: () => now, client: MockClient((request) async {
      if (request.url.path.endsWith('refresh')) rotations++;
      return http.Response(jsonEncode(syntheticSession(refresh: 'rotated-$rotations',
        expires: now.add(const Duration(minutes: 10)).millisecondsSinceEpoch ~/ 1000)), 200);
    }));
    await controller.login('synthetic@example.com', 'synthetic-password');
    now = now.add(const Duration(minutes: 11));
    await controller.accessToken();
    expect(rotations, 1);
    expect((await store.read())!.refreshToken, 'rotated-1');
  });
  test('logout during refresh revokes the successor without resurrection', () async {
    final store = SessionStore(storage: MemoryCredentials());
    final gate = Completer<http.Response>();
    final started = Completer<void>();
    final controller = SessionController(store: store, apiUrl: 'https://api.invalid', client: MockClient((request) async {
      if (request.url.path.endsWith('refresh')) { started.complete(); return gate.future; }
      if (request.url.path.endsWith('logout')) {
        expect(jsonDecode(request.body), {'refresh_token': 'successor'});
        return http.Response('', 204);
      }
      return sessionResponse();
    }));
    await controller.login('synthetic@example.com', 'synthetic-password');
    final refresh = controller.refresh();
    await started.future;
    final logout = controller.logout();
    gate.complete(sessionResponse(refresh: 'successor'));
    await Future.wait([refresh, logout]);
    expect(controller.isAuthenticated, false);
    expect(await store.read(), null);
  });
  test('credential POSTs do not follow redirects', () async {
    final controller = SessionController(store: SessionStore(storage: MemoryCredentials()), apiUrl: 'https://api.invalid', client: MockClient((request) async {
      expect(request.followRedirects, false);
      return http.Response('', 307, headers: {'location': 'http://unsafe.invalid'});
    }));
    await expectLater(controller.login('synthetic@example.com', 'synthetic-password'), throwsA(isA<SessionException>()));
    expect(controller.isAuthenticated, false);
  });
  test('storage failure revokes received credentials and never signs in', () async {
    final paths = <String>[];
    final controller = SessionController(store: SessionStore(storage: UnavailableCredentials()), apiUrl: 'https://api.invalid', client: MockClient((request) async {
      paths.add(request.url.path);
      return request.url.path.endsWith('logout') ? http.Response('', 204) : sessionResponse();
    }));
    await expectLater(controller.login('synthetic@example.com', 'synthetic-password'), throwsA(isA<SessionException>()));
    expect(paths, ['/v1/auth/login', '/v1/auth/logout']);
    expect(controller.isAuthenticated, false);
  });
}
