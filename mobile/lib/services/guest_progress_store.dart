import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class GuestProgressStore {
  GuestProgressStore({Future<Directory> Function()? directory}) : _directory = directory ?? getApplicationSupportDirectory;
  static const maxBytes = 32 * 1024;
  static const maxCompleted = 100;
  static const maxChecklists = 10;
  static const fileName = 'phase4_guest_progress.json';
  final Future<Directory> Function() _directory;
  Future<void> _writeQueue = Future.value();

  Future<T> _serialized<T>(Future<T> Function() operation) {
    final next = _writeQueue.then((_) => operation());
    _writeQueue = next.then<void>((_) {}, onError: (Object _, StackTrace __) {});
    return next;
  }

  Future<File> _file() async {
    final root = await _directory();
    await root.create(recursive: true);
    return File('${root.path}${Platform.pathSeparator}$fileName');
  }

  Future<Map<String, dynamic>> _read() async {
    final file = await _file();
    if (!await file.exists()) return {'schema_version': 1, 'completed': <String>[]};
    try {
      final raw = await file.readAsString();
      if (raw.length > maxBytes) throw const FormatException();
      final value = jsonDecode(raw);
      if (value is! Map<String, dynamic> || value['schema_version'] != 1 || value['completed'] is! List) throw const FormatException();
      final completed = (value['completed'] as List).whereType<String>().toSet().take(maxCompleted).toList();
      return {...value, 'completed': completed};
    } catch (_) {
      await _clear();
      return {'schema_version': 1, 'completed': <String>[]};
    }
  }

  Future<bool> contains(String itemId) => _serialized(() async => (await _read())['completed'].contains(itemId));

  Future<void> setCompleted(String itemId, bool completed, {String jurisdiction = 'IN', String language = 'en', int? catalogRevision}) =>
      _serialized(() => _setCompleted(itemId, completed, jurisdiction: jurisdiction, language: language, catalogRevision: catalogRevision));

  Future<void> _setCompleted(String itemId, bool completed, {required String jurisdiction, required String language, required int? catalogRevision}) async {
    if (itemId.isEmpty || itemId.length > 100) return;
    final value = await _read();
    final ids = (value['completed'] as List).whereType<String>().toSet();
    if (completed) {
      ids.add(itemId);
    } else {
      ids.remove(itemId);
    }
    if (ids.length > maxCompleted) return;
    final next = <String, dynamic>{'schema_version': 1, 'jurisdiction': jurisdiction, 'language': language,
      'catalog_revision': catalogRevision, 'completed': ids.toList()};
    final encoded = jsonEncode(next);
    if (encoded.length > maxBytes) return;
    final file = await _file();
    final temporary = File('${file.path}.${DateTime.now().microsecondsSinceEpoch}.tmp');
    await temporary.writeAsString(encoded, flush: true);
    await temporary.rename(file.path);
  }

  Future<void> clear() => _serialized(_clear);

  Future<void> _clear() async {
    final file = await _file();
    if (await file.exists()) await file.delete();
  }
}
