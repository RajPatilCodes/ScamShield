import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:shared_preferences/shared_preferences.dart';

abstract interface class CredentialStorage {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> delete(String key);
}

class PlatformCredentialStorage implements CredentialStorage {
  final FlutterSecureStorage _storage = const FlutterSecureStorage(
    aOptions: AndroidOptions(encryptedSharedPreferences: true,
      keyCipherAlgorithm: KeyCipherAlgorithm.RSA_ECB_OAEPwithSHA_256andMGF1Padding,
      storageCipherAlgorithm: StorageCipherAlgorithm.AES_GCM_NoPadding),
    iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device),
  );
  @override Future<String?> read(String key) => _storage.read(key: key);
  @override Future<void> write(String key, String value) => _storage.write(key: key, value: value);
  @override Future<void> delete(String key) => _storage.delete(key: key);
}

class StoredSession {
  const StoredSession({required this.refreshToken, required this.apiUrl, this.pendingLogout = false});
  final String refreshToken;
  final String apiUrl;
  final bool pendingLogout;
}

class SessionStore {
  SessionStore({CredentialStorage? storage}) : _storage = storage ?? PlatformCredentialStorage();
  final CredentialStorage _storage;
  static const key = 'scamshield.refresh.v1';

  Future<void> removeLegacyToken() async {
    await (await SharedPreferences.getInstance()).remove('token');
  }

  Future<StoredSession?> read() async {
    final value = await _storage.read(key);
    if (value == null) return null;
    try {
      final json = jsonDecode(value) as Map<String, dynamic>;
      if (json['refresh_token'] is! String || (json['refresh_token'] as String).isEmpty ||
          json['api_url'] is! String || json['pending_logout'] is! bool) {
        throw const FormatException('Invalid stored credential');
      }
      return StoredSession(refreshToken: json['refresh_token'] as String,
        apiUrl: json['api_url'] as String, pendingLogout: json['pending_logout'] as bool);
    } on FormatException {
      await clear();
      rethrow;
    } on TypeError {
      await clear();
      throw const FormatException('Invalid stored credential');
    }
  }

  Future<void> write(StoredSession session) => _storage.write(key, jsonEncode({
    'refresh_token': session.refreshToken, 'api_url': session.apiUrl, 'pending_logout': session.pendingLogout,
  }));
  Future<void> clear() => _storage.delete(key);
}
