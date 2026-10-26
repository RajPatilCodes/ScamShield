import 'dart:async';
import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;

import '../models/catalog.dart';
import 'catalog_cache.dart';
import 'guest_progress_store.dart';
import 'session_controller.dart';

class CatalogException implements Exception {
  const CatalogException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
  @override
  String toString() => message;
}

typedef CatalogBodyValidator = void Function(Map<String, dynamic> body);
typedef CatalogDecoder<T> = T Function(Map<String, dynamic> value);

class CatalogService {
  CatalogService({required this.client, required this.sessions, required this.apiUrl,
    CatalogCacheStore? cache, GuestProgressStore? progress})
      : cache = cache ?? CatalogCacheStore(),
        progress = progress ?? GuestProgressStore(),
        _wasAuthenticated = sessions.isAuthenticated {
    sessions.addListener(_sessionChanged);
  }

  final http.Client client;
  final SessionController sessions;
  final String apiUrl;
  final CatalogCacheStore cache;
  final GuestProgressStore progress;
  bool _wasAuthenticated;
  bool _lastResponseWasFallback = false;
  bool _lastResponseWasBundled = false;
  bool _lastResponseWasStale = false;
  int? _lastCatalogRevision;

  bool get lastResponseWasFallback => _lastResponseWasFallback;
  bool get lastResponseWasBundled => _lastResponseWasBundled;
  bool get lastResponseWasStale => _lastResponseWasStale;
  int? get lastCatalogRevision => _lastCatalogRevision;
  static const defaultLanguage = 'en';
  static const jurisdiction = 'IN';
  static const maxCacheAge = Duration(days: 7);
  static final _digestPattern = RegExp(r'^[0-9a-f]{64}$');

  void _sessionChanged() {
    final next = sessions.isAuthenticated;
    if (next || (_wasAuthenticated && !next)) unawaited(_clearProgressSafely());
    _wasAuthenticated = next;
  }

  Future<void> _clearProgressSafely() async {
    try {
      await progress.clear();
    } catch (_) {
      // Guest progress is best-effort local state; it must never create an
      // unhandled asynchronous error during an account transition.
    }
  }

  Future<void> setGuestProgress(String itemId, bool completed, {required String language}) async {
    if (sessions.isAuthenticated) return;
    final generation = sessions.generation;
    await progress.setCompleted(itemId, completed, language: language, catalogRevision: lastCatalogRevision);
    if (sessions.isAuthenticated || sessions.generation != generation) {
      await _clearProgressSafely();
    }
  }

  Future<Map<String, dynamic>> _cached(String key, CatalogBodyValidator validate) async {
    final entry = await cache.read(key);
    final body = entry?['body'];
    final revision = entry?['revision'];
    final digest = entry?['digest'];
    final cachedAt = entry?['cached_at'];
    final revisionNumber = revision is String ? int.tryParse(revision) : null;
    if (body is! Map<String, dynamic> || revisionNumber == null || revisionNumber < 1 ||
        digest is! String || !_digestPattern.hasMatch(digest) || cachedAt is! int || cachedAt < 0) {
      await cache.remove(key);
      throw const CatalogException('Cached public content was invalid.');
    }
    final normalized = Map<String, dynamic>.from(body);
    try {
      validate(normalized);
    } catch (_) {
      await cache.remove(key);
      throw const CatalogException('Cached public content was invalid.');
    }
    final age = DateTime.now().millisecondsSinceEpoch - cachedAt;
    _lastCatalogRevision = revisionNumber;
    _lastResponseWasStale = age < 0 || age > maxCacheAge.inMilliseconds;
    return normalized;
  }

  Future<Map<String, dynamic>> _get(String path, {String? asset, required CatalogBodyValidator validate}) async {
    final key = '$jurisdiction:${Uri.parse(path).queryParameters['language'] ?? defaultLanguage}:$path';
    _lastResponseWasFallback = false;
    _lastResponseWasBundled = false;
    _lastResponseWasStale = false;
    _lastCatalogRevision = null;
    CatalogException failure = const CatalogException('Public content is unavailable offline.');
    try {
      SessionController.validateCredentialUrl(apiUrl);
      final response = await client.get(Uri.parse('$apiUrl$path')).timeout(const Duration(seconds: 15));
      if (response.statusCode >= 200 && response.statusCode < 300) {
        final decoded = jsonDecode(response.body);
        if (decoded is! Map<String, dynamic> || jsonEncode(decoded).length > CatalogCacheStore.maxEntryBytes) {
          throw const CatalogException('Public content was invalid.');
        }
        final revision = response.headers['x-catalog-revision'];
        final digest = response.headers['x-catalog-digest'];
        final revisionNumber = revision == null ? null : int.tryParse(revision);
        if (revisionNumber == null || revisionNumber < 1 || digest == null || !_digestPattern.hasMatch(digest)) {
          throw const CatalogException('Public content integrity metadata was invalid.');
        }
        validate(decoded);
        _lastCatalogRevision = revisionNumber;
        try {
          await cache.write(key, {
            'revision': revision,
            'digest': digest,
            'etag': response.headers['etag'],
            'cached_at': DateTime.now().millisecondsSinceEpoch,
            'body': decoded,
          });
        } catch (_) {
          // A cache write failure must not turn a valid online response into
          // an unavailable result. The emergency bundle remains independent.
        }
        return decoded;
      }
      failure = CatalogException('Public content is unavailable.', statusCode: response.statusCode);
    } on CatalogException catch (error) {
      failure = error;
    } catch (_) {
      failure = const CatalogException('Public content is unavailable offline.');
    }

    try {
      final body = await _cached(key, validate);
      _lastResponseWasFallback = true;
      return body;
    } catch (_) {
      // A corrupt or incomplete cache must not block the bundled emergency fallback.
    }
    if (asset != null) {
      try {
        final body = await _asset(asset);
        validate(body);
        _lastResponseWasFallback = true;
        _lastResponseWasBundled = true;
        _lastResponseWasStale = false;
        _lastCatalogRevision = null;
        return body;
      } catch (_) {
        // Normalize asset failures to the same public-content error below.
      }
    }
    throw failure;
  }

  Future<Map<String, dynamic>> _asset(String asset) async {
    final decoded = jsonDecode(await rootBundle.loadString(asset));
    if (decoded is List) return {'items': decoded, 'next_cursor': null};
    if (decoded is Map<String, dynamic>) return decoded;
    throw const CatalogException('Bundled public content was invalid.');
  }

  String _query(String path, String language, {String? cursor, int? limit, String? q, String? categoryId}) {
    final params = <String, String>{
      'jurisdiction': jurisdiction,
      'language': language,
      if (cursor != null && cursor.isNotEmpty) 'cursor': cursor,
      if (limit != null) 'limit': '$limit',
      if (q != null) 'q': q,
      if (categoryId != null && categoryId.isNotEmpty) 'category_id': categoryId,
    };
    return Uri(path: path, queryParameters: params).toString();
  }

  List<dynamic> _items(Map<String, dynamic> body) {
    final items = body['items'];
    if (items is! List) throw const CatalogException('Public content was invalid.');
    return items;
  }

  List<T> _parseItems<T>(Map<String, dynamic> body, CatalogDecoder<T> decode) =>
      _items(body).map((item) => decode(Map<String, dynamic>.from(item as Map))).toList();

  Future<List<T>> _list<T>(String path, CatalogDecoder<T> decode, {String? asset}) async {
    final body = await _get(path, asset: asset, validate: (value) {
      _parseItems(value, decode);
    });
    return _parseItems(body, decode);
  }

  Future<T> _detail<T>(String path, CatalogDecoder<T> decode, {String? asset}) async {
    final body = await _get(path, asset: asset, validate: (value) {
      decode(value);
    });
    return decode(body);
  }

  Future<List<CatalogCategory>> categories({String language = defaultLanguage}) =>
      _list(_query('/v1/catalog/categories', language), CatalogCategory.fromJson);

  Future<List<CatalogGuide>> guides({String language = defaultLanguage, String? cursor, int limit = 20, String? categoryId}) =>
      _list(_query('/v1/catalog/guides', language, cursor: cursor, limit: limit, categoryId: categoryId), CatalogGuide.fromJson);

  Future<CatalogGuide> guide(String id, {String language = defaultLanguage}) =>
      _detail(_query('/v1/catalog/guides/$id', language), CatalogGuide.fromJson);

  Future<List<CatalogGuide>> search(String query, {String language = defaultLanguage, String? cursor, int limit = 20, String? categoryId}) =>
      _list(_query('/v1/catalog/search', language, cursor: cursor, limit: limit, q: query, categoryId: categoryId), CatalogGuide.fromJson);

  Future<List<EmergencyPlaybook>> emergencyPlaybooks({String language = defaultLanguage, String? cursor, int limit = 20}) =>
      _list(_query('/v1/emergency/playbooks', language, cursor: cursor, limit: limit), EmergencyPlaybook.fromJson,
        asset: 'assets/phase4/emergency_$language.json');

  Future<EmergencyPlaybook> emergencyPlaybook(String id, {String language = defaultLanguage}) async {
    try {
      return await _detail(_query('/v1/emergency/playbooks/$id', language), EmergencyPlaybook.fromJson,
        asset: 'assets/phase4/emergency_$language.json');
    } catch (_) {
      final items = await emergencyPlaybooks(language: language);
      return items.firstWhere((item) => item.id == id, orElse: () => throw const CatalogException('Emergency playbook is unavailable.'));
    }
  }

  Future<List<LearningLesson>> lessons({String language = defaultLanguage}) =>
      _list(_query('/v1/learning/lessons', language), LearningLesson.fromJson);

  Future<List<LearningChecklist>> checklists({String language = defaultLanguage}) =>
      _list(_query('/v1/checklists', language), LearningChecklist.fromJson);

  Future<List<TrustedResource>> resources({String language = defaultLanguage}) =>
      _list(_query('/v1/resources', language), TrustedResource.fromJson);
}
