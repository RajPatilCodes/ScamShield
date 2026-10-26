class LanguageMetadata {
  const LanguageMetadata({required this.requested, required this.content, required this.fallback});
  final String requested;
  final String content;
  final bool fallback;
  factory LanguageMetadata.fromJson(Map<String, dynamic> json) => LanguageMetadata(
    requested: json['requested_language'] as String,
    content: json['content_language'] as String,
    fallback: json['fallback_used'] as bool,
  );
}

class CatalogCategory {
  const CatalogCategory({required this.id, required this.title, required this.summary, required this.language});
  final String id;
  final String title;
  final String summary;
  final LanguageMetadata language;
  factory CatalogCategory.fromJson(Map<String, dynamic> json) => CatalogCategory(
    id: json['id'] as String, title: json['title'] as String, summary: json['summary'] as String,
    language: LanguageMetadata.fromJson(json['language'] as Map<String, dynamic>),
  );
}

class CatalogGuide {
  const CatalogGuide({required this.id, required this.categoryId, required this.title, required this.summary,
    required this.scenario, required this.warningSigns, required this.safeActions, required this.recoveryGuidance,
    required this.reportingGuidance, required this.preventionTips, required this.falsePositiveNotes,
    required this.resourceIds, required this.lessonIds, required this.reviewStatus, required this.contentVersion,
    required this.language});
  final String id;
  final String categoryId;
  final String title;
  final String summary;
  final String scenario;
  final List<String> warningSigns;
  final List<String> safeActions;
  final List<String> recoveryGuidance;
  final List<String> reportingGuidance;
  final List<String> preventionTips;
  final List<String> falsePositiveNotes;
  final List<String> resourceIds;
  final List<String> lessonIds;
  final String reviewStatus;
  final String contentVersion;
  final LanguageMetadata language;
  factory CatalogGuide.fromJson(Map<String, dynamic> json) => CatalogGuide(
    id: json['id'] as String, categoryId: json['category_id'] as String, title: json['title'] as String,
    summary: json['summary'] as String, scenario: json['scenario'] as String,
    warningSigns: List<String>.from(json['warning_signs'] as List), safeActions: List<String>.from(json['safe_actions'] as List),
    recoveryGuidance: List<String>.from(json['recovery_guidance'] as List), reportingGuidance: List<String>.from(json['reporting_guidance'] as List),
    preventionTips: List<String>.from(json['prevention_tips'] as List), falsePositiveNotes: List<String>.from(json['false_positive_notes'] as List),
    resourceIds: List<String>.from(json['resource_ids'] as List), lessonIds: List<String>.from(json['lesson_ids'] as List),
    reviewStatus: json['review_status'] as String, contentVersion: json['content_version'] as String,
    language: LanguageMetadata.fromJson(json['language'] as Map<String, dynamic>),
  );
}

class EmergencyPlaybook {
  const EmergencyPlaybook({required this.id, required this.title, required this.summary, required this.immediateActions,
    required this.preserveEvidence, required this.recoveryActions, required this.escalationGuidance,
    required this.reviewStatus, required this.contentVersion, required this.language});
  final String id;
  final String title;
  final String summary;
  final List<String> immediateActions;
  final List<String> preserveEvidence;
  final List<String> recoveryActions;
  final List<String> escalationGuidance;
  final String reviewStatus;
  final String contentVersion;
  final LanguageMetadata language;
  factory EmergencyPlaybook.fromJson(Map<String, dynamic> json) => EmergencyPlaybook(
    id: json['id'] as String, title: json['title'] as String, summary: json['summary'] as String,
    immediateActions: List<String>.from(json['immediate_actions'] as List), preserveEvidence: List<String>.from(json['preserve_evidence'] as List),
    recoveryActions: List<String>.from(json['recovery_actions'] as List), escalationGuidance: List<String>.from(json['escalation_guidance'] as List),
    reviewStatus: json['review_status'] as String, contentVersion: json['content_version'] as String,
    language: LanguageMetadata.fromJson(json['language'] as Map<String, dynamic>),
  );
}

class KnowledgeCheck {
  const KnowledgeCheck({required this.id, required this.question, required this.options,
    required this.correctOption, required this.explanation});
  final String id;
  final String question;
  final List<String> options;
  final int correctOption;
  final String explanation;

  factory KnowledgeCheck.fromJson(Map<String, dynamic> json) => KnowledgeCheck(
    id: json['id'] as String,
    question: json['question'] as String,
    options: List<String>.from(json['options'] as List),
    correctOption: json['correct_option'] as int,
    explanation: json['explanation'] as String,
  );
}

class LearningLesson {
  const LearningLesson({required this.id, required this.title, required this.summary, required this.sections,
    required this.knowledgeChecks, required this.reviewStatus, required this.contentVersion, required this.language});
  final String id;
  final String title;
  final String summary;
  final List<Map<String, dynamic>> sections;
  final List<KnowledgeCheck> knowledgeChecks;
  final String reviewStatus;
  final String contentVersion;
  final LanguageMetadata language;
  factory LearningLesson.fromJson(Map<String, dynamic> json) => LearningLesson(
    id: json['id'] as String, title: json['title'] as String, summary: json['summary'] as String,
    sections: (json['sections'] as List).map((item) => Map<String, dynamic>.from(item as Map)).toList(),
    knowledgeChecks: (json['knowledge_checks'] as List).map((item) => KnowledgeCheck.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    reviewStatus: json['review_status'] as String, contentVersion: json['content_version'] as String,
    language: LanguageMetadata.fromJson(json['language'] as Map<String, dynamic>),
  );
}

class ChecklistItem {
  const ChecklistItem({required this.id, required this.label});
  final String id;
  final String label;
  factory ChecklistItem.fromJson(Map<String, dynamic> json) => ChecklistItem(id: json['id'] as String, label: json['label'] as String);
}

class LearningChecklist {
  const LearningChecklist({required this.id, required this.title, required this.summary, required this.items,
    required this.reviewStatus, required this.contentVersion, required this.language});
  final String id;
  final String title;
  final String summary;
  final List<ChecklistItem> items;
  final String reviewStatus;
  final String contentVersion;
  final LanguageMetadata language;
  factory LearningChecklist.fromJson(Map<String, dynamic> json) => LearningChecklist(
    id: json['id'] as String, title: json['title'] as String, summary: json['summary'] as String,
    items: (json['items'] as List).map((item) => ChecklistItem.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    reviewStatus: json['review_status'] as String, contentVersion: json['content_version'] as String,
    language: LanguageMetadata.fromJson(json['language'] as Map<String, dynamic>),
  );
}

class TrustedResource {
  const TrustedResource({required this.id, required this.name, required this.jurisdiction, required this.destination,
    required this.publisher, required this.sourceReferences, required this.verificationStatus, required this.verificationDate,
    required this.nextReviewAt, required this.contentDigest, required this.withdrawn, required this.language});
  final String id;
  final String name;
  final String jurisdiction;
  final String? destination;
  final String publisher;
  final List<String> sourceReferences;
  final String verificationStatus;
  final int? verificationDate;
  final int? nextReviewAt;
  final String? contentDigest;
  final bool withdrawn;
  final LanguageMetadata language;
  factory TrustedResource.fromJson(Map<String, dynamic> json) => TrustedResource(
    id: json['id'] as String, name: json['name'] as String, jurisdiction: json['jurisdiction'] as String,
    destination: json['destination'] as String?, publisher: json['publisher'] as String,
    sourceReferences: List<String>.from(json['source_references'] as List), verificationStatus: json['verification_status'] as String,
    verificationDate: json['verification_date'] as int?, nextReviewAt: json['next_review_at'] as int?,
    contentDigest: json['content_digest'] as String?, withdrawn: json['withdrawn'] as bool,
    language: LanguageMetadata.fromJson(json['language'] as Map<String, dynamic>),
  );
}
