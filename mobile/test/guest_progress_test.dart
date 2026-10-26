import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:scamshield_mobile/services/api_service.dart';
import 'package:scamshield_mobile/services/guest_progress_store.dart';
import 'package:scamshield_mobile/services/session_store.dart';

import 'session_controller_test.dart' show syntheticSession;
import 'session_store_test.dart' show MemoryCredentials;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory root;

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    root = await Directory.systemTemp.createTemp('scamshield-guest-progress-');
  });

  tearDown(() async {
    if (await root.exists()) await root.delete(recursive: true);
  });

  test('guest progress is local and can be explicitly reset', () async {
    final store = GuestProgressStore(directory: () async => root);
    await store.setCompleted('checklist:first', true);
    expect(await store.contains('checklist:first'), true);
    await store.clear();
    expect(await store.contains('checklist:first'), false);
  });

  test('guest progress records the catalog revision without storing account data', () async {
    final store = GuestProgressStore(directory: () async => root);
    await store.setCompleted('checklist:first', true, language: 'en', catalogRevision: 7);
    final file = File('${root.path}${Platform.pathSeparator}phase4_guest_progress.json');
    final value = jsonDecode(await file.readAsString()) as Map<String, dynamic>;
    expect(value['catalog_revision'], 7);
    expect(value.keys, isNot(contains('account_id')));
    expect(value.keys, isNot(contains('email')));
  });

  test('account transitions clear guest progress without a network progress call', () async {
    final progress = GuestProgressStore(directory: () async => root);
    await progress.setCompleted('checklist:first', true);
    var progressRequests = 0;
    final api = ApiService(
      apiUrl: 'https://api.invalid',
      sessionStore: SessionStore(storage: MemoryCredentials()),
      guestProgress: progress,
      client: MockClient((request) async {
        if (request.url.path == '/v1/auth/login') return http.Response(jsonEncode(syntheticSession()), 200);
        progressRequests++;
        return http.Response('{}', 200);
      }),
    );

    await api.authenticate('guest@example.com', 'password123');
    await Future<void>.delayed(Duration.zero);
    expect(await progress.contains('checklist:first'), false);
    expect(progressRequests, 0);

    await progress.setCompleted('checklist:second', true);
    await api.signOut();
    await Future<void>.delayed(Duration.zero);
    expect(await progress.contains('checklist:second'), false);
  });
}
