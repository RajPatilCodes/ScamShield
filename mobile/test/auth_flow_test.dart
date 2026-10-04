import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:scamshield_mobile/main.dart';
import 'package:scamshield_mobile/screens/home_screen.dart';
import 'package:scamshield_mobile/screens/verify_email_screen.dart';
import 'package:scamshield_mobile/screens/password_recovery_screen.dart';
import 'package:scamshield_mobile/services/api_service.dart';
import 'package:scamshield_mobile/services/session_store.dart';
import 'session_store_test.dart' show MemoryCredentials;
import 'session_controller_test.dart' show syntheticSession;

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));
  testWidgets('registration requires email verification and never signs in', (tester) async {
    final memory = MemoryCredentials();
    final api = ApiService(sessionStore: SessionStore(storage: memory), client: MockClient((request) async {
      expect(request.url.path, '/v1/auth/register');
      return http.Response('{"message":"If eligible, check your email."}', 201);
    }));
    await tester.pumpWidget(ScamShieldApp(api: api, signedIn: false));
    await tester.ensureVisible(find.text('New to ScamShield? Create account'));
    await tester.tap(find.text('New to ScamShield? Create account'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, 'Email address'), 'synthetic@example.com');
    await tester.enterText(find.widgetWithText(TextField, 'Password'), 'synthetic-password');
    await tester.ensureVisible(find.text('Create account'));
    await tester.tap(find.text('Create account'));
    await tester.pumpAndSettle();
    expect(find.text('Confirm email'), findsOneWidget);
    expect(await api.isSignedIn(), false);
    expect(memory.values, isEmpty);
  });
  testWidgets('central invalidation removes all private routes and history state', (tester) async {
    final api = ApiService(sessionStore: SessionStore(storage: MemoryCredentials()), client: MockClient((request) async {
      if (request.url.path.endsWith('login')) return http.Response(jsonEncode(syntheticSession()), 200);
      if (request.url.path.endsWith('logout')) return http.Response('', 204);
      return http.Response('{"items":[{"id":1,"content":"synthetic private history","score":5,"verdict":"low-risk","created_at":"2026-01-01T00:00:00"}],"total":1,"page":1,"page_size":100}', 200);
    }));
    await api.authenticate('synthetic@example.com', 'synthetic-password');
    await tester.pumpWidget(ScamShieldApp(api: api, signedIn: true));
    await tester.pumpAndSettle();
    expect(find.byType(HomeScreen), findsOneWidget);
    expect(find.text('synthetic private history'), findsWidgets);
    await api.sessions.invalidate();
    await tester.pumpAndSettle();
    expect(find.byType(HomeScreen, skipOffstage: false), findsNothing);
    expect(find.text('synthetic private history', skipOffstage: false), findsNothing);
    expect(find.text('Welcome to ScamShield'), findsOneWidget);
  });
  test('401 refresh failure invalidates the session centrally', () async {
    final api = ApiService(sessionStore: SessionStore(storage: MemoryCredentials()), client: MockClient((request) async {
      return request.url.path.endsWith('login') ? http.Response(jsonEncode(syntheticSession()), 200) : http.Response('{}', 401);
    }));
    await api.authenticate('synthetic@example.com', 'synthetic-password');
    await expectLater(api.history(), throwsA(isA<MediaScanException>()));
    expect(await api.isSignedIn(), false);
  });
  testWidgets('verification consumes the input without storing a secret or creating a session', (tester) async {
    final memory = MemoryCredentials();
    final api = ApiService(sessionStore: SessionStore(storage: memory), client: MockClient((request) async {
      expect(request.url.path, '/v1/auth/verification/confirm');
      expect(jsonDecode(request.body), {'token': 'synthetic-verification'});
      return http.Response('', 204);
    }));
    await tester.pumpWidget(MaterialApp(home: VerifyEmailScreen(api: api, email: 'synthetic@example.com')));
    await tester.enterText(find.widgetWithText(TextField, 'Verification credential'), 'synthetic-verification');
    await tester.tap(find.text('Confirm email'));
    await tester.pumpAndSettle();
    expect(find.text('Email verified. Return to sign in.'), findsOneWidget);
    expect(tester.widget<TextField>(find.widgetWithText(TextField, 'Verification credential')).controller!.text, isEmpty);
    expect(memory.values, isEmpty);
    expect(await api.isSignedIn(), false);
  });
  testWidgets('recovery consumes and clears the secret and replacement password', (tester) async {
    final memory = MemoryCredentials();
    final api = ApiService(sessionStore: SessionStore(storage: memory), client: MockClient((request) async {
      expect(request.url.path, '/v1/auth/recovery/confirm');
      expect(jsonDecode(request.body), {'token': 'synthetic-recovery', 'password': 'synthetic-replacement'});
      return http.Response('', 204);
    }));
    await tester.pumpWidget(MaterialApp(home: PasswordRecoveryScreen(api: api)));
    await tester.enterText(find.widgetWithText(TextField, 'Recovery credential'), 'synthetic-recovery');
    await tester.enterText(find.widgetWithText(TextField, 'New password'), 'synthetic-replacement');
    await tester.tap(find.text('Replace password'));
    await tester.pumpAndSettle();
    expect(find.text('Password replaced. Sign in with your new password.'), findsOneWidget);
    for (final label in ['Recovery credential', 'New password']) {
      expect(tester.widget<TextField>(find.widgetWithText(TextField, label)).controller!.text, isEmpty);
    }
    expect(memory.values, isEmpty);
  });
  test('offline logout exposes pending server revocation and blocks restoration', () async {
    final store = SessionStore(storage: MemoryCredentials());
    final api = ApiService(sessionStore: store, client: MockClient((request) async {
      if (request.url.path.endsWith('login')) return http.Response(jsonEncode(syntheticSession()), 200);
      throw http.ClientException('synthetic offline');
    }));
    await api.authenticate('synthetic@example.com', 'synthetic-password');
    await api.signOut();
    expect(await api.isSignedIn(), false);
    expect((await store.read())!.pendingLogout, true);
    expect(api.sessions.notice, contains('Server revocation is pending'));
    expect(await api.restoreSession(), false);
  });
  testWidgets('rapid account switch cannot retain the previous private navigation tree', (tester) async {
    var owner = '';
    final api = ApiService(sessionStore: SessionStore(storage: MemoryCredentials()), client: MockClient((request) async {
      if (request.url.path.endsWith('login')) {
        owner = jsonDecode(request.body)['email'] as String;
        return http.Response(jsonEncode(syntheticSession()), 200);
      }
      if (owner == 'first@example.com') {
        return http.Response('{"items":[{"id":1,"content":"previous account private data","score":5,"verdict":"low-risk","created_at":"2026-01-01T00:00:00"}]}', 200);
      }
      return http.Response('{"items":[]}', 200);
    }));
    await api.authenticate('first@example.com', 'synthetic-password');
    await tester.pumpWidget(ScamShieldApp(api: api, signedIn: true));
    await tester.pumpAndSettle();
    expect(find.text('previous account private data'), findsWidgets);
    // Both changes deliberately occur before another frame, even with the same
    // synthetic session identifier: the transition epoch must still dispose it.
    await api.sessions.invalidate();
    await api.authenticate('second@example.com', 'synthetic-password');
    await tester.pumpAndSettle();
    expect(find.text('previous account private data', skipOffstage: false), findsNothing);
    expect(find.byType(HomeScreen, skipOffstage: false), findsOneWidget);
  });
}
