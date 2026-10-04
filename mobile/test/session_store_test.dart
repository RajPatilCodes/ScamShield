import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:scamshield_mobile/services/session_store.dart';

class MemoryCredentials implements CredentialStorage {
  final values = <String, String>{};
  @override Future<String?> read(String key) async => values[key];
  @override Future<void> write(String key, String value) async { values[key] = value; }
  @override Future<void> delete(String key) async { values.remove(key); }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({'token': 'legacy-bearer'}));
  test('removes legacy bearer without transferring it to protected storage', () async {
    final memory = MemoryCredentials();
    final store = SessionStore(storage: memory);
    await store.removeLegacyToken();
    expect((await SharedPreferences.getInstance()).containsKey('token'), false);
    expect(memory.values, isEmpty);
  });
  test('only durable refresh and its API binding are stored', () async {
    final memory = MemoryCredentials();
    final store = SessionStore(storage: memory);
    await store.write(const StoredSession(refreshToken: 'synthetic-refresh', apiUrl: 'https://api.invalid'));
    final json = jsonDecode(memory.values[SessionStore.key]!);
    expect(json.keys.toSet(), {'refresh_token', 'api_url', 'pending_logout'});
    expect((await store.read())!.refreshToken, 'synthetic-refresh');
    await store.clear();
    expect(await store.read(), null);
  });
  test('pending revocation survives process restart', () async {
    final memory = MemoryCredentials();
    await SessionStore(storage: memory).write(const StoredSession(refreshToken: 'synthetic-refresh', apiUrl: 'https://api.invalid', pendingLogout: true));
    expect((await SessionStore(storage: memory).read())!.pendingLogout, true);
  });
  test('malformed durable state is rejected', () async {
    final memory = MemoryCredentials()..values[SessionStore.key] = '{}';
    await expectLater(SessionStore(storage: memory).read(), throwsFormatException);
    expect(memory.values, isEmpty);
  });
  test('platform adapter delegates only to the protected native credential channel', () async {
    const channel = MethodChannel('plugins.it_nomads.com/flutter_secure_storage');
    final calls = <MethodCall>[];
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(channel, (call) async { calls.add(call); return null; });
    addTearDown(() {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger.setMockMethodCallHandler(channel, null);
    });
    await PlatformCredentialStorage().write('synthetic-key', 'synthetic-refresh');
    expect(calls.single.method, 'write');
    expect(calls.single.arguments['key'], 'synthetic-key');
    expect(calls.single.arguments['value'], 'synthetic-refresh');
    expect((await SharedPreferences.getInstance()).getString('synthetic-key'), null);
  });
  test('Android release forbids HTTP; debug permits only approved local address', () {
    final release = File('android/app/src/main/res/xml/network_security_config.xml').readAsStringSync();
    final debug = File('android/app/src/debug/res/xml/network_security_config.xml').readAsStringSync();
    expect(release, isNot(contains('cleartextTrafficPermitted="true"')));
    expect(RegExp(r'<domain\s[^>]*>([^<]+)</domain>').allMatches(debug).map((match) => match.group(1)).toList(), ['10.0.2.2']);
  });
  test('Android cloud backup and device transfer exclude credential files', () {
    final manifest = File('android/app/src/main/AndroidManifest.xml').readAsStringSync();
    expect(manifest, contains('android:fullBackupContent="@xml/backup_rules"'));
    expect(manifest, contains('android:dataExtractionRules="@xml/data_extraction_rules"'));
    final backup = File('android/app/src/main/res/xml/backup_rules.xml').readAsStringSync();
    final transfer = File('android/app/src/main/res/xml/data_extraction_rules.xml').readAsStringSync();
    for (final name in ['FlutterSecureStorage.xml', 'FlutterSecureKeyStorage.xml', 'FlutterSharedPreferences.xml']) {
      expect(backup, contains('path="$name"'));
      expect('path="$name"'.allMatches(transfer).length, 2);
    }
  });
}
