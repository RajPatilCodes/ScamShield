class ScanResult {
  const ScanResult({required this.score, required this.level, required this.reasons, required this.actions, required this.content, this.createdAt, this.contentType, this.sizeBytes, this.sha256});
  final String? contentType;
  final int? sizeBytes;
  final String? sha256;
  bool get isMedia => contentType != null;
  final int score;
  final String level;
  final List<String> reasons;
  final List<String> actions;
  final String content;
  final DateTime? createdAt;

  factory ScanResult.fromJson(Map<String, dynamic> json) => ScanResult(
    score: (json['score'] as num).toInt(),
    level: json['verdict'] as String,
    reasons: List<String>.from(json['flags'] ?? const []),
    actions: List<String>.from(json['actions'] ?? const []),
    content: json['content'] as String? ?? '',
    createdAt: DateTime.tryParse(json['created_at'] as String? ?? ''),
  );
  factory ScanResult.fromMediaJson(Map<String, dynamic> json) {
    if (!['unverified', 'review'].contains(json['verdict']) || json['malware_scanned'] != false) {
      throw const FormatException('Unexpected media screening response');
    }
    return ScanResult(score: 0, level: json['verdict'] as String,
      reasons: List<String>.from(json['flags'] as List), actions: List<String>.from(json['actions'] as List),
      content: json['filename'] as String, contentType: json['content_type'] as String,
      sizeBytes: json['size_bytes'] as int, sha256: json['sha256'] as String, createdAt: DateTime.now());
  }
}
