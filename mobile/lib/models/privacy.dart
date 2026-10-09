class PrivacySettings {
  const PrivacySettings({required this.purpose, required this.notice, required this.noticeVersion,
    required this.preferenceVersion, required this.savingEnabled, required this.artifactHours, this.exportMaxBytes = 100000000});
  final String purpose;
  final String notice;
  final String noticeVersion;
  final int preferenceVersion;
  final bool savingEnabled;
  final int artifactHours;
  final int exportMaxBytes;
  factory PrivacySettings.fromJson(Map<String, dynamic> json) => PrivacySettings(
    purpose: json['purpose'] as String, notice: json['notice'] as String,
    noticeVersion: json['notice_version'] as String, preferenceVersion: json['preference_version'] as int,
    savingEnabled: json['saving_enabled'] as bool, artifactHours: json['artifact_hours'] as int,
    exportMaxBytes: json['export_max_bytes'] as int? ?? 100000000);
}

class PrivacyJob {
  const PrivacyJob({required this.id, required this.kind, required this.state, this.errorCode, this.totalBytes = 0});
  final String id;
  final String kind;
  final String state;
  final String? errorCode;
  final int totalBytes;
  bool get pending => state == 'queued' || state == 'retrying';
  factory PrivacyJob.fromJson(Map<String, dynamic> json) => PrivacyJob(id: json['id'] as String,
    kind: json['kind'] as String, state: json['state'] as String,
    errorCode: json['error_code'] as String?, totalBytes: json['total_bytes'] as int? ?? 0);
}

class PrivateContext {
  const PrivateContext(this.apiUrl, this.owner, this.sessionId, this.generation);
  final String apiUrl;
  final String owner;
  final String sessionId;
  final int generation;
  String get accountKey => '$apiUrl|$owner|$sessionId';
  String get requestKey => '$accountKey|$generation';
}

class PrivacyException implements Exception {
  const PrivacyException(this.message);
  final String message;
  @override String toString() => message;
}
