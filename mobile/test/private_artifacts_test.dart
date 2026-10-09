import 'dart:convert';
import 'dart:io';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter/services.dart';
import 'package:scamshield_mobile/models/privacy.dart';
import 'package:scamshield_mobile/services/private_artifacts.dart';
import 'package:scamshield_mobile/services/privacy_store.dart';
import 'session_store_test.dart' show MemoryCredentials;

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late Directory temp;
  const a = PrivateContext('https://api.invalid', '1', 'session-a', 1);
  const b = PrivateContext('https://api.invalid', '2', 'session-b', 2);
  final payload = utf8.encode('${jsonEncode({'type': 'manifest', 'format_version': 1})}\n${jsonEncode({'type': 'end', 'complete': true})}\n');
  setUp(() async { temp = await Directory.systemTemp.createTemp('phase3-mobile-'); });
  tearDown(() async { await temp.delete(recursive: true); });
  test('picker stream refuses chunks when the source expires during consumption', () async {
    var now = DateTime.utc(2030);
    final artifacts = PrivateArtifacts(temporaryDirectory: () async => temp, now: () => now)..bind(a);
    final original = File('${temp.path}${Platform.pathSeparator}picker.jpg');
    await original.writeAsBytes([1, 2, 3]);
    final copy = await artifacts.adoptPickerCopy(a, original.path);
    Stream<List<int>> source() async* {
      yield [1];
      now = now.add(const Duration(hours: 24));
      yield [2, 3];
    }
    final received = <int>[];
    await expectLater(artifacts.checkedRead(a, copy.path, source()).forEach(received.addAll), throwsA(isA<PrivacyException>()));
    expect(received, [1]);
  });
  test('delayed document handoff carries original deadline and refuses late completion', () async {
    var now = DateTime.utc(2030);
    const channel = MethodChannel('phase3-delayed-handoff');
    final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
    messenger.setMockMethodCallHandler(channel, (call) async {
      expect(call.method, 'saveExport');
      final arguments = call.arguments as Map;
      expect(arguments['expiresAt'], now.add(const Duration(hours: 24)).millisecondsSinceEpoch);
      expect(arguments['owner'], a.accountKey);
      now = now.add(const Duration(hours: 24));
      return true; // Even a late success from the platform cannot publish a usable result.
    });
    try {
      final artifacts = PrivateArtifacts(temporaryDirectory: () async => temp, now: () => now, channel: channel)..bind(a);
      final file = await artifacts.download(a, Stream.value(payload), payload.length);
      await expectLater(artifacts.saveUserCopy(a, file), throwsA(isA<PrivacyException>()));
    } finally { messenger.setMockMethodCallHandler(channel, null); }
  });
  test('streamed export completes, expires at 24h, and preserves external user copy', () async {
    var now = DateTime.utc(2030);
    final artifacts = PrivateArtifacts(temporaryDirectory: () async => temp, now: () => now)..bind(a);
    final file = await artifacts.download(a, Stream.fromIterable(payload.map((byte) => [byte])), payload.length);
    final external = File('${temp.path}${Platform.pathSeparator}user-copy.jsonl');
    await external.writeAsBytes(payload);
    now = now.add(const Duration(hours: 24));
    await artifacts.prepare(a);
    expect(await file.exists(), false);
    expect(await external.exists(), true);
  });
  test('partial and switched-account exports never remain available', () async {
    final artifacts = PrivateArtifacts(temporaryDirectory: () async => temp)..bind(a);
    await expectLater(artifacts.download(a, Stream.value(payload.sublist(0, 10)), payload.length), throwsA(anything));
    final file = await artifacts.download(a, Stream.value(payload), payload.length);
    artifacts.bind(b);
    await artifacts.ready;
    expect(await file.exists(), false);
    await expectLater(artifacts.download(a, Stream.value(payload), payload.length), throwsA(isA<PrivacyException>()));
  });
  test('picker recovery binds API owner session and survives legitimate restoration', () async {
    final store = PrivacyStore(storage: MemoryCredentials());
    final now = DateTime.utc(2030);
    await store.beginPicker(a, now);
    expect(await store.recoverPicker(b, now), isNull);
    await store.beginPicker(a, now);
    expect(await store.recoverPicker(const PrivateContext('https://api.invalid', '1', 'session-a', 0), now), isNotNull);
    await store.beginPicker(a, now);
    expect(await store.recoverPicker(a, now.add(const Duration(hours: 24))), isNull);
  });
  test('picker lease expiry is preserved and expired selection cannot be adopted', () async {
    var now = DateTime.utc(2030);
    final store = PrivacyStore(storage: MemoryCredentials());
    final deadline = await store.beginPicker(a, now);
    final original = File('${temp.path}${Platform.pathSeparator}gallery.jpg');
    await original.writeAsBytes([1, 2, 3]);
    now = now.add(const Duration(hours: 24));
    expect(await store.recoverPicker(a, now), isNull);
    final artifacts = PrivateArtifacts(temporaryDirectory: () async => temp, now: () => now)..bind(a);
    await expectLater(artifacts.adoptPickerCopy(a, original.path, expiresAt: deadline), throwsA(isA<PrivacyException>()));
    expect(await original.exists(), true);
    final appRoot = Directory('${temp.path}${Platform.pathSeparator}scamshield-private');
    expect(await appRoot.list().toList(), isEmpty);
  });
  test('picker adoption retains the original lease deadline', () async {
    var now = DateTime.utc(2030);
    final store = PrivacyStore(storage: MemoryCredentials());
    final deadline = await store.beginPicker(a, now);
    now = now.add(const Duration(hours: 1));
    final original = File('${temp.path}${Platform.pathSeparator}gallery-valid.jpg');
    await original.writeAsBytes([1, 2, 3]);
    final artifacts = PrivateArtifacts(temporaryDirectory: () async => temp, now: () => now)..bind(a);
    final copy = await artifacts.adoptPickerCopy(a, original.path, expiresAt: deadline);
    final metadata = jsonDecode(await File('${copy.path}.meta').readAsString()) as Map<String, dynamic>;
    expect(metadata['expires_at'], deadline);
    expect(await original.exists(), true);
  });
  test('artifact cleanup never deletes an original outside the app temporary root', () async {
    final outside = await Directory.systemTemp.createTemp('phase3-original-');
    try {
      final original = File('${outside.path}${Platform.pathSeparator}original.jpg');
      await original.writeAsBytes([1, 2, 3]);
      final artifacts = PrivateArtifacts(temporaryDirectory: () async => temp)..bind(a);
      await artifacts.discardPickerCopy(original.path);
      expect(await original.exists(), true);
    } finally { await outside.delete(recursive: true); }
  });
  test('a large JSONL record streams to disk without a complete-record accumulator', () async {
    final artifacts = PrivateArtifacts(temporaryDirectory: () async => temp)..bind(a);
    final header = utf8.encode('{"type":"manifest","format_version":1}\n{"type":"analysis","content":"');
    final block = utf8.encode('x' * 10000);
    final ending = utf8.encode('"}\n{"type":"end","complete":true}\n');
    Stream<List<int>> source() async* {
      yield header;
      for (var index = 0; index < 100; index++) { yield block; }
      yield ending;
    }
    final expected = header.length + block.length * 100 + ending.length;
    final file = await artifacts.download(a, source(), expected);
    expect(await file.length(), expected);
  });
  test('startup removes a previous account artifact before restoration', () async {
    final old = PrivateArtifacts(temporaryDirectory: () async => temp)..bind(a);
    final file = await old.download(a, Stream.value(payload), payload.length);
    final restarted = PrivateArtifacts(temporaryDirectory: () async => temp);
    await restarted.initialise();
    expect(await file.exists(), false);
  });
  test('failed startup cleanup keeps private access gated until an explicit retry', () async {
    var failed = true;
    final artifacts = PrivateArtifacts(temporaryDirectory: () async {
      if (failed) throw const FileSystemException('synthetic cleanup unavailable');
      return temp;
    });
    await expectLater(artifacts.initialise(), throwsA(isA<FileSystemException>()));
    await expectLater(artifacts.ready, throwsA(isA<PrivacyException>()));
    failed = false;
    await artifacts.initialise();
    await artifacts.ready;
  });
}
