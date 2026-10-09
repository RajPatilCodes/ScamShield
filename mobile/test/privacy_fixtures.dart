import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:scamshield_mobile/services/api_service.dart';
import 'package:scamshield_mobile/services/session_store.dart';
import 'package:scamshield_mobile/services/privacy_store.dart';
import 'package:scamshield_mobile/services/private_artifacts.dart';
import 'session_store_test.dart' show MemoryCredentials;

Map<String, dynamic> privacySession({String owner = '1', String sid = '00000000-0000-4000-8000-000000000001'}) {
  final claims = base64Url.encode(utf8.encode(jsonEncode({'sub': owner, 'sid': sid, 'purpose': 'access',
    'exp': DateTime.now().add(const Duration(minutes: 10)).millisecondsSinceEpoch ~/ 1000}))).replaceAll('=', '');
  return {'access_token': 'synthetic.$claims.signature', 'refresh_token': 'synthetic-refresh',
    'session_id': sid, 'token_type': 'bearer', 'expires_in': 600};
}

Map<String, dynamic> privacySettings({bool enabled = false}) => {'purpose': 'saved_analysis_storage',
  'notice': 'Synthetic product saving notice, not a legal notice.', 'notice_version': 'product-1',
  'preference_version': 0, 'saving_enabled': enabled, 'artifact_hours': 24};

http.Response jsonResponse(Object body, [int status = 200]) => http.Response(jsonEncode(body), status);

ApiService privacyApi(http.Client client, {Directory? temp, MemoryCredentials? storage}) {
  final memory = storage ?? MemoryCredentials();
  return ApiService(client: client, apiUrl: 'https://api.invalid', sessionStore: SessionStore(storage: memory),
    privacyStore: PrivacyStore(storage: memory), privateArtifacts: PrivateArtifacts(
      temporaryDirectory: temp == null ? null : () async => temp));
}
