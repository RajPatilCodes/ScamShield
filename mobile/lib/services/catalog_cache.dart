import 'dart:convert';
import 'dart:io';

import 'package:path_provider/path_provider.dart';

class CatalogCacheStore {
  CatalogCacheStore({Future<Directory> Function()? directory}) : _directory = directory ?? getApplicationSupportDirectory;
  static const maxEntryBytes = 2 * 1024 * 1024;
  static const maxTotalBytes = 8 * 1024 * 1024;
  static const fileName = 'phase4_public_catalog_cache.json';
  final Future<Directory> Function() _directory;
  Future<void> _writeQueue = Future.value();

  Future<void> _serialized(Future<void> Function() operation) {
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
    if (!await file.exists()) return {};
    try {
      final raw = await file.readAsString();
      if (raw.length > maxTotalBytes) throw const FormatException();
      final value = jsonDecode(raw);
      return value is Map<String, dynamic> ? value : <String, dynamic>{};
    } catch (_) {
      await file.delete();
      return {};
    }
  }

  Future<Map<String, dynamic>?> read(String key) async {
    await _writeQueue;
    return (await _read())[key] as Map<String, dynamic>?;
  }

  Future<void> write(String key, Map<String, dynamic> entry) => _serialized(() => _write(key, entry));

  Future<void> _write(String key, Map<String, dynamic> entry) async {
    final encodedEntry = jsonEncode(entry);
    if (encodedEntry.length > maxEntryBytes) return;
    final values = await _read();
    values[key] = entry;
    var encoded = jsonEncode(values);
    if (encoded.length > maxTotalBytes) {
      values.remove(key);
      final keys = values.keys.toList()..sort();
      while (encoded.length > maxTotalBytes && keys.isNotEmpty) {
        values.remove(keys.removeAt(0));
        encoded = jsonEncode(values);
      }
      if (encodedEntry.length <= maxTotalBytes) values[key] = entry;
      encoded = jsonEncode(values);
      if (encoded.length > maxTotalBytes) return;
    }
    final file = await _file();
    final temporary = File('${file.path}.${DateTime.now().microsecondsSinceEpoch}.tmp');
    await temporary.writeAsString(encoded, flush: true);
    await temporary.rename(file.path);
  }

  Future<void> remove(String key) => _serialized(() => _remove(key));

  Future<void> _remove(String key) async {
    final values = await _read();
    if (!values.containsKey(key)) return;
    values.remove(key);
    final file = await _file();
    final temporary = File('${file.path}.${DateTime.now().microsecondsSinceEpoch}.tmp');
    await temporary.writeAsString(jsonEncode(values), flush: true);
    await temporary.rename(file.path);
  }

  Future<void> clear() => _serialized(_clear);

  Future<void> _clear() async {
    final file = await _file();
    if (await file.exists()) await file.delete();
  }
}
