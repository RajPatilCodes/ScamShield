import 'dart:convert';

class AuthSession {
  const AuthSession({required this.accessToken, required this.refreshToken,
    required this.sessionId, required this.expiresAt, required this.ownerId});
  final String accessToken;
  final String refreshToken;
  final String sessionId;
  final DateTime expiresAt;
  final String ownerId;

  factory AuthSession.fromJson(Map<String, dynamic> json) {
    final access = json['access_token'];
    final refresh = json['refresh_token'];
    final sid = json['session_id'];
    if (access is! String || refresh is! String || sid is! String ||
        access.isEmpty || refresh.isEmpty || sid.isEmpty ||
        json['token_type'] != 'bearer' || json['expires_in'] != 600) {
      throw const FormatException('Invalid session response');
    }
    final parts = access.split('.');
    if (parts.length != 3) throw const FormatException('Invalid access credential');
    final claims = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
    if (claims is! Map<String, dynamic> || claims['exp'] is! int ||
        claims['purpose'] != 'access' || claims['sid'] != sid || claims['sub'] is! String) {
      throw const FormatException('Invalid access claims');
    }
    final expiry = DateTime.fromMillisecondsSinceEpoch((claims['exp'] as int) * 1000, isUtc: true);
    if (!expiry.isAfter(DateTime.now())) throw const FormatException('Expired access credential');
    return AuthSession(accessToken: access, refreshToken: refresh, sessionId: sid, expiresAt: expiry, ownerId: claims['sub'] as String);
  }
}
