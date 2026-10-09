import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../models/auth_session.dart';
import 'session_store.dart';

class SessionException implements Exception {
  const SessionException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
}

class SessionController extends ChangeNotifier {
  SessionController({required this.client, required this.store, required this.apiUrl, DateTime Function()? now}) : _now = now ?? DateTime.now;
  final DateTime Function() _now;
  final http.Client client;
  final SessionStore store;
  final String apiUrl;
  AuthSession? _session;
  String? _notice;
  String? get notice => _notice;
  Future<void>? _refreshing;
  Future<void>? _loggingIn;
  Future<void> _storageQueue = Future.value();
  int _generation = 0;
  int get generation => _generation;
  bool get isAuthenticated => _session != null;
  AuthSession? get session => _session;

  static void validateCredentialUrl(String value, {bool debug = kDebugMode}) {
    final uri = Uri.parse(value);
    if (!uri.hasAuthority || uri.host.isEmpty || uri.userInfo.isNotEmpty || uri.hasQuery || uri.hasFragment ||
        (uri.path.isNotEmpty && uri.path != '/') ||
        (uri.scheme != 'https' && !(debug && uri.scheme == 'http' && uri.host == '10.0.2.2' && uri.port == 8000))) {
      throw const SessionException('Use HTTPS for the API; debug HTTP is restricted to 10.0.2.2:8000.');
    }
  }

  Future<http.Response> post(String path, Map<String, dynamic> body, {String? targetUrl}) async {
    final target = targetUrl ?? apiUrl;
    validateCredentialUrl(target);
    try {
      final request = http.Request('POST', Uri.parse('$target/v1/auth/$path'))
        ..followRedirects = false
        ..headers['Content-Type'] = 'application/json'
        ..body = jsonEncode(body);
      final response = await client.send(request).then(http.Response.fromStream).timeout(const Duration(seconds: 90));
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw SessionException(switch (response.statusCode) {
          401 => 'Authentication failed. Check your credentials or sign in again.',
          400 => 'This verification or recovery credential is invalid or expired.',
          422 => 'Check your email and password. Passwords must be 8–1,024 characters and at most 4,096 UTF-8 bytes.',
          429 => 'Too many attempts. Please try again later.',
          _ => 'Authentication service unavailable. Please try again.',
        }, statusCode: response.statusCode);
      }
      return response;
    } on TimeoutException {
      throw const SessionException('Authentication request timed out. Please try again.');
    } on http.ClientException {
      throw const SessionException('Cannot reach the authentication service.');
    }
  }

  Future<T> _storage<T>(Future<T> Function() operation) {
    final next = _storageQueue.then((_) => operation());
    _storageQueue = next.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return next;
  }

  Future<void> login(String email, String password) {
    if (_loggingIn != null) return Future.error(const SessionException('A sign-in is already in progress.'));
    final operation = _login(email, password);
    _loggingIn = operation.whenComplete(() => _loggingIn = null);
    return _loggingIn!;
  }

  Future<void> _login(String email, String password) async {
    await store.removeLegacyToken();
    // Never overwrite an outstanding revocation or another account's durable session.
    if (await _storage(store.read) != null) {
      await _markPendingLogout();
      await _revokeStored();
    }
    final generation = ++_generation;
    final response = await post('login', {'email': email.trim(), 'password': password});
    await _accept(response, generation);
  }

  Future<void> _accept(http.Response response, int generation) async {
    AuthSession? received;
    try {
      final next = AuthSession.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
      received = next;
      await _storage(() async {
        await store.write(StoredSession(refreshToken: next.refreshToken, apiUrl: apiUrl,
          pendingLogout: generation != _generation));
        if (generation != _generation) return;
        _session = next;
        _notice = null;
        notifyListeners();
      });
    } on FormatException {
      throw const SessionException('The service did not return a valid session.');
    } on TypeError {
      throw const SessionException('The service did not return a valid session.');
    } catch (_) {
      _session = null;
      notifyListeners();
      if (received != null) {
        try { await post('logout', {'refresh_token': received.refreshToken}); } catch (_) { /* Remain signed out on storage failure. */ }
      }
      throw const SessionException('Protected credential storage is unavailable. Please try again.');
    }
  }

  Future<bool> restore() async {
    await store.removeLegacyToken();
    try {
      final stored = await _storage(store.read);
      if (stored == null) return false;
      if (stored.apiUrl != apiUrl) {
        await logout();
        return false;
      }
      if (stored.pendingLogout) {
        await logout();
        return false;
      }
      await refresh();
      return isAuthenticated;
    } catch (_) {
      _session = null;
      notifyListeners();
      return false;
    }
  }

  Future<String> accessToken() async {
    if (_session == null || !_session!.expiresAt.isAfter(_now())) await refresh();
    final current = _session;
    if (current == null) throw const SessionException('Please sign in again.');
    return current.accessToken;
  }

  Future<void> refresh() {
    if (_refreshing != null) return _refreshing!;
    final generation = _generation;
    final operation = _rotate(generation);
    _refreshing = operation.whenComplete(() => _refreshing = null);
    return _refreshing!;
  }

  Future<void> _rotate(int generation) async {
    try {
      final stored = await _storage(store.read);
      if (stored == null || stored.pendingLogout || stored.apiUrl != apiUrl) {
        throw const SessionException('Please sign in again.');
      }
      final response = await post('refresh', {'refresh_token': stored.refreshToken});
      await _accept(response, generation);
    } catch (error) {
      if (generation == _generation) {
        if (error is SessionException && error.statusCode == 401) {
          await invalidate();
        } else {
          // An uncertain refresh may already have rotated. Do not replay it.
          await _markPendingLogout();
        }
      }
      rethrow;
    }
  }

  Future<void> _markPendingLogout() async {
    ++_generation;
    _session = null;
    _notice = 'Signed out locally. Server revocation is pending; reconnect to finish logout.';
    notifyListeners();
    await _storage(() async {
      final stored = await store.read();
      if (stored != null) {
        await store.write(StoredSession(refreshToken: stored.refreshToken,
          apiUrl: stored.apiUrl, pendingLogout: true));
      }
    });
  }

  Future<void> invalidate() async {
    ++_generation;
    _session = null;
    _notice = 'Session expired or revoked. Please sign in again.';
    notifyListeners();
    await _storage(store.clear);
    await store.removeLegacyToken();
  }

  Future<void> logout() async {
    await _markPendingLogout();
    // A late successful login/refresh must be revoked too, never resurrected.
    for (final pending in [_loggingIn, _refreshing]) {
      try { await pending; } catch (_) { /* Revoke with the last known family credential. */ }
    }
    await _revokeStored();
  }

  Future<void> _revokeStored() async {
    final stored = await _storage(store.read);
    if (stored != null) {
      await post('logout', {'refresh_token': stored.refreshToken}, targetUrl: stored.apiUrl);
    }
    await _storage(store.clear);
    await store.removeLegacyToken();
    _notice = null;
    notifyListeners();
  }
}
