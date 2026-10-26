import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:scamshield_mobile/models/catalog.dart';
import 'package:scamshield_mobile/services/api_service.dart';
import 'package:scamshield_mobile/services/catalog_cache.dart';
import 'package:scamshield_mobile/services/catalog_service.dart';
import 'package:scamshield_mobile/services/guest_progress_store.dart';

Map<String, dynamic> guide(String id) => {
  'id': id,
  'category_id': 'payments',
  'title': 'Payment request',
  'summary': 'Check before paying.',
  'scenario': 'A request is unexpected.',
  'warning_signs': ['Pressure'],
  'safe_actions': ['Pause'],
  'recovery_guidance': ['Contact the provider'],
  'reporting_guidance': ['Keep records'],
  'prevention_tips': ['Verify independently'],
  'false_positive_notes': ['A genuine request can still be verified.'],
  'resource_ids': <String>[],
  'lesson_ids': <String>[],
  'review_status': 'pending_editorial_review',
  'content_version': '1.0.0',
  'language': {'requested_language': 'en', 'content_language': 'en', 'fallback_used': false},
};

Map<String, dynamic> guidePage({Object? items}) => {
  'items': items ?? [guide('SC-001')],
  'next_cursor': null,
};

http.Response catalogResponse(Object body, {int status = 200}) => http.Response(
  jsonEncode(body),
  status,
  headers: {
    'x-catalog-revision': '1',
    'x-catalog-digest': 'a' * 64,
    'etag': '"catalog-1-${'a' * 16}"',
  },
);

ApiService apiFor(http.Client client, Directory root) => ApiService(
  client: client,
  apiUrl: 'https://api.invalid',
  catalogCache: CatalogCacheStore(directory: () async => root),
  guestProgress: GuestProgressStore(directory: () async => root),
);

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory root;

  setUp(() async {
    root = await Directory.systemTemp.createTemp('scamshield-catalog-test-');
  });

  tearDown(() async {
    if (await root.exists()) await root.delete(recursive: true);
  });

  test('valid responses are cached and reused offline', () async {
    final api = apiFor(MockClient((_) async => catalogResponse(guidePage())), root);
    expect((await api.catalog.guides(limit: 20)).single, isA<CatalogGuide>());

    final offline = apiFor(MockClient((_) async => throw http.ClientException('offline')), root);
    final values = await offline.catalog.guides(limit: 20);
    expect(values.single.id, 'SC-001');
    expect(offline.catalog.lastResponseWasFallback, true);
    expect(offline.catalog.lastResponseWasBundled, false);
  });

  test('an invalid update preserves the last known-good cache', () async {
    final api = apiFor(MockClient((_) async => catalogResponse(guidePage())), root);
    await api.catalog.guides(limit: 20);

    final invalid = apiFor(MockClient((_) async => catalogResponse({'unexpected': true})), root);
    final values = await invalid.catalog.guides(limit: 20);
    expect(values.single.id, 'SC-001');
    expect(invalid.catalog.lastResponseWasFallback, true);
  });

  test('stale cached content remains usable and reports its revision and age', () async {
    final api = apiFor(MockClient((_) async => catalogResponse(guidePage())), root);
    await api.catalog.guides(limit: 20);
    const key = 'IN:en:/v1/catalog/guides?jurisdiction=IN&language=en&limit=20';
    final cache = CatalogCacheStore(directory: () async => root);
    final entry = await cache.read(key);
    expect(entry, isNotNull);
    entry!['cached_at'] = DateTime.now().subtract(const Duration(days: 8)).millisecondsSinceEpoch;
    await cache.write(key, entry);

    final offline = apiFor(MockClient((_) async => throw http.ClientException('offline')), root);
    expect((await offline.catalog.guides(limit: 20)).single.id, 'SC-001');
    expect(offline.catalog.lastResponseWasFallback, true);
    expect(offline.catalog.lastResponseWasStale, true);
    expect(offline.catalog.lastCatalogRevision, 1);
  });

  test('concurrent cache writes preserve every bounded entry', () async {
    final cache = CatalogCacheStore(directory: () async => root);
    await Future.wait(List.generate(8, (index) => cache.write('key-$index', {
      'revision': '1',
      'digest': 'a' * 64,
      'cached_at': DateTime.now().millisecondsSinceEpoch,
      'body': {'items': [index]},
    })));
    for (var index = 0; index < 8; index++) {
      expect(await cache.read('key-$index'), isNotNull);
    }
  });

  test('corrupt cached content is rejected rather than decoded as trusted content', () async {
    final cache = CatalogCacheStore(directory: () async => root);
    await cache.write('IN:en:/v1/catalog/guides?jurisdiction=IN&language=en&limit=20', {
      'revision': '1',
      'digest': 'a' * 64,
      'cached_at': DateTime.now().millisecondsSinceEpoch,
      'body': {'items': [{'bad': true}], 'next_cursor': null},
    });
    final api = apiFor(MockClient((_) async => throw http.ClientException('offline')), root);
    await expectLater(api.catalog.guides(limit: 20), throwsA(isA<CatalogException>()));
  });

  test('both essential emergency playbooks are bundled for offline use', () async {
    final raw = await rootBundle.loadString('assets/phase4/emergency_en.json');
    expect(raw, contains('account-takeover'));
    final api = apiFor(MockClient((_) async => throw http.ClientException('offline')), root);
    final values = await api.catalog.emergencyPlaybooks(language: 'en');
    expect(values.map((item) => item.id), containsAll(<String>['urgent-payment-or-account', 'account-takeover']));
    expect(api.catalog.lastResponseWasBundled, true);
  });
}
