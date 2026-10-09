import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:scamshield_mobile/services/privacy_store.dart';
import 'package:scamshield_mobile/screens/privacy_screen.dart';
import 'package:scamshield_mobile/screens/scan_screen.dart';
import 'package:scamshield_mobile/screens/home_screen.dart';
import 'dart:async';
import 'package:http/http.dart' as http;
import 'session_store_test.dart' show MemoryCredentials;
import 'privacy_fixtures.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUp(() => SharedPreferences.setMockInitialValues({}));
  testWidgets('bulk deletion clears cached history and fences a late old history response', (tester) async {
    final oldHistory = Completer<http.Response>();
    final historyStarted = Completer<void>();
    var reads = 0;
    final item = {'id': 7, 'record_key': '00000000-0000-4000-8000-000000000007',
      'content': 'obsolete saved record', 'score': 0, 'verdict': 'low-risk'};
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      if (request.url.path == '/analysis/history') {
        if (++reads == 1) return jsonResponse({'items': [item]});
        historyStarted.complete();
        return oldHistory.future;
      }
      return jsonResponse({'id': 'delete-job', 'kind': 'deletion', 'state': 'queued'}, 202);
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    await tester.pumpWidget(MaterialApp(home: HomeScreen(api: api)));
    await tester.pumpAndSettle();
    expect(find.text('obsolete saved record'), findsOneWidget);
    await tester.tap(find.text('History'));
    await tester.pumpAndSettle();
    await tester.tap(find.byTooltip('Refresh history'));
    await tester.pump();
    await tester.runAsync(() async {
      await historyStarted.future;
      await api.privacy.deleteSaved('single-use-grant');
      oldHistory.complete(jsonResponse({'items': [item]}));
    });
    await tester.pumpAndSettle();
    expect(find.text('obsolete saved record'), findsNothing);
  });
  test('ordinary scan stays transient; explicit save has a separate strict request', () async {
    final paths = <String>[];
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      paths.add(request.url.path);
      if (request.url.path == '/analysis/analyze') {
        expect(jsonDecode(request.body), {'content': 'hello'});
        return jsonResponse({'score': 0, 'verdict': 'low-risk', 'flags': <String>[]});
      }
      expect(jsonDecode(request.body), {'content': 'hello', 'save': true});
      expect(request.headers['Idempotency-Key'], isNotEmpty);
      return jsonResponse({'id': 7, 'record_key': '00000000-0000-4000-8000-000000000007', 'content': 'hello',
        'score': 0, 'verdict': 'low-risk', 'flags': <String>[], 'saved': true,
        'created_at': DateTime.now().toIso8601String(), 'expires_at': 2000000000, 'provenance': 'current_consent'}, 201);
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    expect((await api.scan('hello')).isSaved, false);
    expect((await api.scan('hello', save: true)).savedId, 7);
    expect(paths, ['/analysis/analyze', '/v1/privacy/analyses']);
  });
  test('account receipt is protected before submission; successful deletion clears authentication', () async {
    final memory = MemoryCredentials();
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      final pending = jsonDecode(memory.values[PrivacyStore.receiptKey]!) as Map<String, dynamic>;
      expect(jsonDecode(request.body)['receipt'], pending['receipt']);
      return jsonResponse({'id': 'job', 'kind': 'deletion', 'state': 'queued'}, 202);
    }), storage: memory);
    await api.authenticate('synthetic@example.com', 'password123');
    await api.privacy.deleteAccount('single-action-grant');
    expect(api.sessions.isAuthenticated, false);
    expect(memory.values.containsKey(PrivacyStore.receiptKey), true);
    expect(memory.values.containsKey('scamshield.refresh.v1'), false);
  });
  test('a re-registered account never reuses an earlier deletion receipt', () async {
    final memory = MemoryCredentials();
    var login = 0;
    final receipts = <String>[];
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) {
        login++;
        return jsonResponse(privacySession(sid: '00000000-0000-4000-8000-00000000000$login'));
      }
      receipts.add(jsonDecode(request.body)['receipt'] as String);
      return jsonResponse({'id': 'job', 'kind': 'deletion', 'state': 'queued'}, 202);
    }), storage: memory);
    await api.authenticate('synthetic@example.com', 'password123');
    await api.privacy.deleteAccount('first-grant');
    await api.authenticate('synthetic@example.com', 'password123');
    await api.privacy.deleteAccount('second-grant');
    expect(receipts.length, 2);
    expect(receipts.first, isNot(receipts.last));
  });
  testWidgets('scan saving is visibly OFF by default', (tester) async {
    final api = privacyApi(MockClient((_) async => jsonResponse(privacySession())));
    await api.authenticate('synthetic@example.com', 'password123');
    await tester.pumpWidget(MaterialApp(home: ScanScreen(api: api)));
    expect(tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value, false);
    expect(find.textContaining('Off by default'), findsOneWidget);
  });
  testWidgets('privacy screen shows product notice and saving disabled', (tester) async {
    final api = privacyApi(MockClient((request) async {
      if (request.url.path.endsWith('/login')) return jsonResponse(privacySession());
      return jsonResponse(request.url.path.endsWith('/exports') ? {'items': []} : privacySettings());
    }));
    await api.authenticate('synthetic@example.com', 'password123');
    await tester.pumpWidget(MaterialApp(home: PrivacyScreen(privacy: api.privacy)));
    await tester.pumpAndSettle();
    expect(tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value, false);
    expect(find.text('Product data controls — not a legal privacy notice.'), findsOneWidget);
  });
}
