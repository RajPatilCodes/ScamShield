import 'dart:convert';
import 'dart:typed_data';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:image_picker/image_picker.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:scamshield_mobile/services/api_service.dart';
import 'package:scamshield_mobile/models/scan_result.dart';
import 'package:scamshield_mobile/screens/result_screen.dart';
import 'package:scamshield_mobile/services/session_store.dart';
import 'session_store_test.dart' show MemoryCredentials;
import 'session_controller_test.dart' show syntheticSession;

Map<String, dynamic> mediaResponse() => {'filename': 'photo.png', 'content_type': 'image/png', 'size_bytes': 3, 'sha256': 'a' * 64, 'verdict': 'unverified', 'flags': <String>[], 'actions': ['Verify the source'], 'malware_scanned': false};

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  ApiService apiWith(http.Client client) => ApiService(client: client, sessionStore: SessionStore(storage: MemoryCredentials()));
  test('authenticate sends the current login contract', () async {
    final api = apiWith(MockClient((request) async {
      expect(request.method, 'POST');
      expect(request.url.path, '/v1/auth/login');
      expect(request.headers['content-type'], 'application/json');
      expect(jsonDecode(request.body), {
        'email': 'test@example.com',
        'password': 'password123',
      });
      return http.Response(jsonEncode(syntheticSession()), 200);
    }));

    expect(await api.authenticate('test@example.com', 'password123'), true);
    expect(await api.isSignedIn(), true);
  });
  test('failed and malformed login never create a session', () async {
    for (final response in [http.Response('Unavailable', 503), http.Response('{}', 200)]) {
      final api = apiWith(MockClient((_) async => response));
      await expectLater(api.authenticate('test@example.com', 'password'), throwsA(isA<MediaScanException>()));
      expect(await api.isSignedIn(), false);
    }
    SharedPreferences.setMockInitialValues({'token': 'local-session'});
    expect(await ApiService().isSignedIn(), false);
  });
  test('text scan failure does not fabricate a result', () async {
    final api = apiWith(MockClient((request) async => request.url.path.endsWith('login') ? http.Response(jsonEncode(syntheticSession()), 200) : http.Response('Unavailable', 503)));
    await api.authenticate('test@example.com', 'password123');
    await expectLater(api.scan('hello'), throwsA(isA<MediaScanException>()));
  });
  test('media sends authenticated multipart file and parses metadata without score', () async {
    final session = syntheticSession();
    final api = apiWith(MockClient((request) async {
      if (request.url.path.endsWith('login')) return http.Response(jsonEncode(session), 200);
      expect(request.url.path, '/analysis/media');
      expect(request.headers['Authorization'], 'Bearer ${session['access_token']}');
      expect(request.headers['content-type'], startsWith('multipart/form-data;'));
      expect(request.body, contains('name="file"; filename="photo.png"'));
      return http.Response(jsonEncode(mediaResponse()), 200);
    }));
    await api.authenticate('test@example.com', 'password123');
    final result = await api.scanMedia(XFile.fromData(Uint8List.fromList([1, 2, 3]), path: 'photo.png'));
    expect(result.isMedia, true);
    expect(result.sizeBytes, 3);
    expect(result.level, 'unverified');
  });
  test('oversized and unauthenticated media never upload', () async {
    final api = apiWith(MockClient((_) async => throw StateError('must not send')));
    await expectLater(api.scanMedia(XFile.fromData(Uint8List(20 * 1024 * 1024 + 1), name: 'big.mp4')), throwsA(isA<MediaScanException>()));
    await expectLater(api.scanMedia(XFile.fromData(Uint8List(1), name: 'photo.png')), throwsA(isA<MediaScanException>()));
  });
  testWidgets('media result is metadata only and has no risk score', (tester) async {
    await tester.pumpWidget(MaterialApp(home: ResultScreen(result: ScanResult.fromMediaJson(mediaResponse()))));
    expect(find.text('Metadata only'), findsOneWidget);
    expect(find.text('Not malware scanned. Content remains unverified.'), findsOneWidget);
    expect(find.text('0/100'), findsNothing);
  });
}
