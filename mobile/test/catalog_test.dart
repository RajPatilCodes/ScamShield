import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:scamshield_mobile/models/catalog.dart';
import 'package:scamshield_mobile/screens/learning_screen.dart';
import 'package:scamshield_mobile/services/api_service.dart';
import 'package:scamshield_mobile/services/catalog_cache.dart';
import 'package:scamshield_mobile/services/guest_progress_store.dart';

Map<String, dynamic> lessonPage() => {
  'items': [
    {
      'id': 'lesson-pause-verify',
      'title': 'Pause, verify, and protect',
      'summary': 'Slow down before acting.',
      'sections': [{'heading': 'Pause', 'body': 'Stop first.'}],
      'knowledge_checks': [
        {
          'id': 'pause-q1',
          'question': 'What should you do first?',
          'options': ['Pause and verify', 'Share the code'],
          'correct_option': 0,
          'explanation': 'Independent verification reduces pressure.',
        },
      ],
      'review_status': 'pending_editorial_review',
      'content_version': '1.0.0',
      'language': {'requested_language': 'en', 'content_language': 'en', 'fallback_used': false},
    },
  ],
  'next_cursor': null,
};

ApiService lessonApi(Directory root) => ApiService(
  client: MockClient((request) async => http.Response(
    jsonEncode(lessonPage()),
    200,
    headers: {'x-catalog-revision': '1', 'x-catalog-digest': 'a' * 64},
  )),
  apiUrl: 'https://api.invalid',
  catalogCache: CatalogCacheStore(directory: () async => root),
  guestProgress: GuestProgressStore(directory: () async => root),
);

void main() {
  late Directory root;

  setUp(() async {
    root = await Directory.systemTemp.createTemp('scamshield-catalog-widget-');
  });

  tearDown(() async {
    if (await root.exists()) await root.delete(recursive: true);
  });

  test('resource model accepts an explicit null digest', () {
    final resource = TrustedResource.fromJson({
      'id': 'resource-pending',
      'name': 'Pending resource',
      'jurisdiction': 'IN',
      'destination': null,
      'publisher': 'Pending',
      'source_references': <String>[],
      'verification_status': 'unverified',
      'verification_date': null,
      'next_review_at': null,
      'content_digest': null,
      'withdrawn': false,
      'language': {'requested_language': 'en', 'content_language': 'en', 'fallback_used': false},
    });
    expect(resource.contentDigest, isNull);
  });

  testWidgets('learning screen presents a local knowledge check', (tester) async {
    final api = lessonApi(root);
    final lessons = <LearningLesson>[
      const LearningLesson(
        id: 'lesson-pause-verify',
        title: 'Pause, verify, and protect',
        summary: 'Slow down before acting.',
        sections: [{'heading': 'Pause', 'body': 'Stop first.'}],
        knowledgeChecks: [KnowledgeCheck(
          id: 'pause-q1',
          question: 'What should you do first?',
          options: ['Pause and verify', 'Share the code'],
          correctOption: 0,
          explanation: 'Independent verification reduces pressure.',
        )],
        reviewStatus: 'pending_editorial_review',
        contentVersion: '1.0.0',
        language: LanguageMetadata(requested: 'en', content: 'en', fallback: false),
      ),
    ];
    await tester.pumpWidget(MaterialApp(home: LearningScreen(api: api, initialLessons: Future.value(lessons))));
    await tester.pump(const Duration(seconds: 1));

    await tester.tap(find.text('Pause, verify, and protect'));
    await tester.pumpAndSettle();
    final checkButton = find.widgetWithText(OutlinedButton, 'Knowledge check');
    expect(checkButton, findsOneWidget);
    await tester.scrollUntilVisible(checkButton, 300, scrollable: find.byType(Scrollable).first);
    await tester.tap(checkButton);
    await tester.pumpAndSettle();
    expect(find.text('What should you do first?'), findsOneWidget);

    await tester.tap(find.byType(DropdownButtonFormField<int>));
    await tester.pumpAndSettle();
    final options = find.byType(DropdownMenuItem<int>);
    expect(options, findsNWidgets(2));
    await tester.tap(options.first);
    await tester.pump();
    final checkAnswer = find.widgetWithText(FilledButton, 'Check answer');
    expect(tester.widget<FilledButton>(checkAnswer).onPressed, isNotNull);
    await tester.tap(checkAnswer);
    await tester.pump();
    expect(find.text('Correct'), findsOneWidget);
    expect(lessons.single.knowledgeChecks.single.correctOption, 0);
  });
}
