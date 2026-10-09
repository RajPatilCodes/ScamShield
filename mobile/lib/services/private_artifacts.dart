import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/services.dart';
import 'package:path_provider/path_provider.dart';
import '../models/privacy.dart';
import 'privacy_store.dart';

class PrivateArtifacts {
  PrivateArtifacts({Future<Directory> Function()? temporaryDirectory, DateTime Function()? now,
    this.channel = const MethodChannel('scamshield/privacy')}) : _directory = temporaryDirectory ?? getTemporaryDirectory,
      _now = now ?? DateTime.now;
  final Future<Directory> Function() _directory;
  final DateTime Function() _now;
  final MethodChannel channel;
  PrivateContext? _context;
  Directory? _root;
  Future<void> _queue = Future.value();
  Object? _cleanupError;
  Future<void> get ready => _queue.then((_) { if (_cleanupError != null) throw const PrivacyException('Private cleanup failed. Please retry before opening private files.'); });
  Future<void> initialise() async {
    await _queue;
    try {
      final temp = await _directory();
      _root = Directory('${temp.path}${Platform.pathSeparator}scamshield-private');
      await _root!.create(recursive: true);
      if (_cleanupError != null) {
        await for (final entity in _root!.list(followLinks: false)) {
          if (entity is File) await entity.delete();
        }
      }
      await _clean();
      _cleanupError = null;
    } catch (error) { _cleanupError = error; rethrow; }
  }
  void bind(PrivateContext? context) {
    final changed = _context?.requestKey != context?.requestKey;
    _context = context;
    if (!changed || _root == null) return;
    _queue = _queue.then((_) async {
      try { await channel.invokeMethod<void>('cancelExport'); } catch (_) { /* No handoff on unsupported platforms. */ }
      await for (final entity in _root!.list(followLinks: false)) {
        if (entity is File) await entity.delete();
      }
    }).catchError((Object error) { _cleanupError = error; });
  }
  void assertCurrent(PrivateContext context) {
    if (_context?.requestKey != context.requestKey) throw const PrivacyException('Account changed. Please try again.');
  }
  Future<int?> checkUse(PrivateContext context, String path, {bool requireManaged = false}) async {
    assertCurrent(context);
    await ready;
    if (!requireManaged && !File(path).absolute.uri.pathSegments.contains('scamshield-private')) {
      assertCurrent(context);
      return null;
    }
    final temp = await _directory();
    final root = Directory('${temp.path}${Platform.pathSeparator}scamshield-private');
    final file = File(path);
    final managed = file.absolute.path.startsWith('${root.absolute.path}${Platform.pathSeparator}');
    if (!managed && !requireManaged) { assertCurrent(context); return null; }
    try {
      final canonical = await file.resolveSymbolicLinks();
      final canonicalRoot = await root.resolveSymbolicLinks();
      final value = jsonDecode(await File('$path.meta').readAsString()) as Map<String, dynamic>;
      final expiry = value['expires_at'];
      assertCurrent(context);
      if (!managed || !canonical.startsWith('$canonicalRoot${Platform.pathSeparator}') ||
          value['owner'] != context.accountKey || expiry is! int || expiry <= _now().millisecondsSinceEpoch) {
        throw const PrivacyException('Private file expired or unavailable. Please select it again.');
      }
      return expiry;
    } on FileSystemException {
      throw const PrivacyException('Private file expired or unavailable. Please select it again.');
    } on FormatException {
      throw const PrivacyException('Private file expired or unavailable. Please select it again.');
    }
  }
  Stream<List<int>> checkedRead(PrivateContext context, String path, Stream<List<int>> source) async* {
    await checkUse(context, path);
    await for (final chunk in source) {
      await checkUse(context, path);
      yield chunk;
    }
    await checkUse(context, path);
  }
  Future<void> prepare(PrivateContext context) async {
    assertCurrent(context);
    await _queue;
    if (_root == null) {
      final temp = await _directory();
      _root = Directory('${temp.path}${Platform.pathSeparator}scamshield-private');
      await _root!.create(recursive: true);
    }
    try {
      if (_cleanupError != null) {
        await for (final entity in _root!.list(followLinks: false)) {
          if (entity is File) await entity.delete();
        }
      }
      await _clean(); _cleanupError = null;
    }
    catch (error) { _cleanupError = error; rethrow; }
    assertCurrent(context);
  }
  Future<void> _clean() async {
    if (_root == null) return;
    await for (final entity in _root!.list(followLinks: false)) {
      if (entity is! File) continue;
      if (entity.path.endsWith('.meta')) {
        if (await entity.exists() && !await File(entity.path.substring(0, entity.path.length - '.meta'.length)).exists()) await entity.delete();
        continue;
      }
      if (!await entity.exists()) continue;
      final meta = File('${entity.path}.meta');
      var keep = false;
      try {
        final value = jsonDecode(await meta.readAsString()) as Map<String, dynamic>;
        keep = _context != null && value['owner'] == _context!.accountKey && value['expires_at'] is int &&
          (value['expires_at'] as int) > _now().millisecondsSinceEpoch;
      } catch (_) { keep = false; }
      if (!keep) { await entity.delete(); if (await meta.exists()) await meta.delete(); }
    }
  }
  Future<File> download(PrivateContext context, Stream<List<int>> bytes, int expectedBytes,
    {int artifactHours = 24, int maxBytes = 100000000}) async {
    await prepare(context);
    final file = File('${_root!.path}${Platform.pathSeparator}${privateNonce()}.jsonl');
    final meta = File('${file.path}.meta');
    final sink = file.openWrite();
    var size = 0;
    final manifestPrefix = utf8.encode('{"type":"manifest","format_version":1');
    final completion = utf8.encode('{"type":"end","complete":true}\n');
    final prefix = <int>[];
    var tail = <int>[];
    try {
      await meta.writeAsString(jsonEncode({'owner': context.accountKey,
        'expires_at': _now().add(Duration(hours: artifactHours)).millisecondsSinceEpoch}));
      await sink.flush();
      // Validate protocol boundaries/count without accumulating a large JSON
      // record (legacy text can be large). HTTP and disk both apply backpressure.
      await for (final chunk in bytes) {
        await checkUse(context, file.path, requireManaged: true);
        size += chunk.length;
        if (size > maxBytes) throw const PrivacyException('Export exceeds the approved size limit.');
        final needed = manifestPrefix.length + 1 - prefix.length;
        if (needed > 0) prefix.addAll(chunk.take(needed));
        if (chunk.length >= completion.length) {
          tail = chunk.sublist(chunk.length - completion.length);
        } else {
          tail.addAll(chunk);
          if (tail.length > completion.length) tail.removeRange(0, tail.length - completion.length);
        }
        sink.add(chunk);
        await sink.flush();
      }
      await sink.close();
      final validPrefix = prefix.length == manifestPrefix.length + 1 &&
        List.generate(manifestPrefix.length, (index) => prefix[index] == manifestPrefix[index]).every((same) => same) &&
        (prefix.last == ','.codeUnitAt(0) || prefix.last == '}'.codeUnitAt(0));
      final validEnd = tail.length == completion.length &&
        List.generate(completion.length, (index) => tail[index] == completion[index]).every((same) => same);
      if (!validPrefix || !validEnd || size != expectedBytes) throw const PrivacyException('The export download is incomplete.');
      await checkUse(context, file.path, requireManaged: true);
      return file;
    } catch (_) {
      await sink.close();
      if (await file.exists()) await file.delete();
      if (await meta.exists()) await meta.delete();
      rethrow;
    }
  }
  Future<bool> saveUserCopy(PrivateContext context, File file, {int maxBytes = 100000000}) async {
    await prepare(context);
    final path = await file.resolveSymbolicLinks();
    final root = await _root!.resolveSymbolicLinks();
    if (!path.startsWith('$root${Platform.pathSeparator}') || !await file.exists()) throw const PrivacyException('Export expired or unavailable.');
    assertCurrent(context);
    final expiry = await checkUse(context, path, requireManaged: true);
    final saved = await channel.invokeMethod<bool>('saveExport', {'path': path, 'context': context.requestKey,
      'owner': context.accountKey, 'expiresAt': expiry, 'maxBytes': maxBytes}) ?? false;
    assertCurrent(context);
    await checkUse(context, path, requireManaged: true);
    return saved;
  }
  Future<void> discardPickerCopy(String path) async {
    final temp = await _directory();
    final file = File(path);
    if (!await file.exists()) return;
    final canonical = await file.resolveSymbolicLinks();
    final rootDirectory = Directory('${temp.path}${Platform.pathSeparator}scamshield-private');
    if (!await rootDirectory.exists()) return;
    final root = await rootDirectory.resolveSymbolicLinks();
    if (canonical.startsWith('$root${Platform.pathSeparator}')) {
      await file.delete();
      final meta = File('${file.path}.meta');
      if (await meta.exists()) await meta.delete();
    }
  }
  Future<File> adoptPickerCopy(PrivateContext context, String path, {int? expiresAt, int artifactHours = 24}) async {
    await prepare(context);
    final result = File('${_root!.path}${Platform.pathSeparator}${privateNonce()}.picker');
    final deadline = expiresAt ?? _now().add(Duration(hours: artifactHours)).millisecondsSinceEpoch;
    if (deadline <= _now().millisecondsSinceEpoch) {
      throw const PrivacyException('Selected media expired. Please select it again.');
    }
    try {
      await File(path).copy(result.path);
      assertCurrent(context);
      if (deadline <= _now().millisecondsSinceEpoch) {
        throw const PrivacyException('Selected media expired. Please select it again.');
      }
      await File('${result.path}.meta').writeAsString(jsonEncode({'owner': context.accountKey,
        'expires_at': deadline}));
      await checkUse(context, result.path, requireManaged: true);
      await discardPickerCopy(path);
      return result;
    } catch (_) {
      if (await result.exists()) await result.delete();
      final meta = File('${result.path}.meta');
      if (await meta.exists()) await meta.delete();
      rethrow;
    }
  }
}
