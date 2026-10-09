import 'dart:convert';
import 'dart:math';
import 'session_store.dart';
import '../models/privacy.dart';

String privateNonce() {
  final random = Random.secure();
  return base64Url.encode(List<int>.generate(48, (_) => random.nextInt(256))).replaceAll('=', '');
}

class PrivacyStore {
  PrivacyStore({CredentialStorage? storage}) : _storage = storage ?? PlatformCredentialStorage();
  final CredentialStorage _storage;
  static const receiptKey = 'scamshield.privacy.deletion.v1';
  static const pickerKey = 'scamshield.privacy.picker.v1';
  Future<Map<String, dynamic>?> _read(String key) async {
    final value = await _storage.read(key);
    if (value == null) return null;
    try { return jsonDecode(value) as Map<String, dynamic>; }
    catch (_) { await _storage.delete(key); return null; }
  }
  Future<void> saveReceipt(String apiUrl, String receipt, String requestKey, {required String accountKey}) => _storage.write(receiptKey,
    jsonEncode({'api_url': apiUrl, 'account_key': accountKey, 'receipt': receipt, 'request_key': requestKey}));
  Future<Map<String, dynamic>?> receipt(String apiUrl) async {
    final value = await _read(receiptKey);
    return value?['api_url'] == apiUrl ? value : null;
  }
  Future<void> clearReceipt() => _storage.delete(receiptKey);
  Future<int> beginPicker(PrivateContext context, DateTime now, {int artifactHours = 24}) async {
    final expiresAt = now.add(Duration(hours: artifactHours)).millisecondsSinceEpoch;
    await _storage.write(pickerKey, jsonEncode({'account_key': context.accountKey, 'expires_at': expiresAt}));
    return expiresAt;
  }
  Future<int?> recoverPicker(PrivateContext context, DateTime now) async {
    final value = await _read(pickerKey);
    await _storage.delete(pickerKey);
    if (value?['account_key'] == context.accountKey && value?['expires_at'] is int &&
        (value!['expires_at'] as int) > now.millisecondsSinceEpoch) {
      return value['expires_at'] as int;
    }
    return null;
  }
  Future<void> clearPicker() => _storage.delete(pickerKey);
}
