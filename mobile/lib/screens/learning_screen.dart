import 'package:flutter/material.dart';

import '../models/catalog.dart';
import '../services/api_service.dart';

class LearningScreen extends StatefulWidget {
  const LearningScreen({super.key, required this.api, this.language = 'en', this.initialLessons});
  final ApiService api;
  final String language;
  final Future<List<LearningLesson>>? initialLessons;
  @override
  State<LearningScreen> createState() => _LearningScreenState();
}

class _LearningScreenState extends State<LearningScreen> {
  late Future<List<LearningLesson>> future;

  @override
  void initState() {
    super.initState();
    future = widget.initialLessons ?? widget.api.catalog.lessons(language: widget.language);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Learning')),
    body: FutureBuilder<List<LearningLesson>>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError) return _error();
        final lessons = snapshot.data ?? const <LearningLesson>[];
        return ListView(padding: const EdgeInsets.all(20), children: [
          const Text('Short lessons help you slow down and verify before acting.'),
          const SizedBox(height: 12),
          if (widget.api.catalog.lastResponseWasFallback) const Card(
            elevation: 0,
            child: Padding(padding: EdgeInsets.all(14), child: Text('Showing the last known-good public content. It may be out of date.')),
          ),
          ...lessons.map((lesson) => Card(child: ExpansionTile(
            title: Text(lesson.title),
            subtitle: Text(lesson.summary),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            children: [
              ...lesson.sections.map((section) => ListTile(
                title: Text('${section['heading'] ?? ''}'),
                subtitle: Text('${section['body'] ?? ''}'),
              )),
              if (lesson.language.fallback) const ListTile(
                leading: Icon(Icons.translate),
                title: Text('English content shown'),
                subtitle: Text('Hindi content is not available for this lesson yet.'),
              ),
              if (lesson.reviewStatus != 'reviewed') const ListTile(
                leading: Icon(Icons.info_outline),
                title: Text('Draft lesson'),
                subtitle: Text('Editorial review is pending. Use this as educational guidance, not an official determination.'),
              ),
              if (lesson.knowledgeChecks.isNotEmpty)
                Align(
                  alignment: Alignment.centerLeft,
                  child: OutlinedButton.icon(
                    onPressed: () => _openCheck(lesson),
                    icon: const Icon(Icons.quiz_outlined),
                    label: const Text('Knowledge check'),
                  ),
                ),
            ],
          ))),
        ]);
      },
    ),
  );

  Future<void> _openCheck(LearningLesson lesson) async {
    await showDialog<void>(
      context: context,
      builder: (context) => _KnowledgeCheckDialog(checks: lesson.knowledgeChecks),
    );
  }

  Widget _error() => Center(child: Padding(
    padding: const EdgeInsets.all(28),
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      const Icon(Icons.cloud_off, size: 44),
      const SizedBox(height: 12),
      const Text('Lessons are unavailable right now.'),
      TextButton(onPressed: () => setState(() => future = widget.api.catalog.lessons(language: widget.language)), child: const Text('Try again')),
    ]),
  ));
}

class _KnowledgeCheckDialog extends StatefulWidget {
  const _KnowledgeCheckDialog({required this.checks});
  final List<KnowledgeCheck> checks;
  @override
  State<_KnowledgeCheckDialog> createState() => _KnowledgeCheckDialogState();
}

class _KnowledgeCheckDialogState extends State<_KnowledgeCheckDialog> {
  int index = 0;
  int? selected;
  bool submitted = false;

  KnowledgeCheck get check => widget.checks[index];

  void submit() {
    if (selected == null) return;
    setState(() => submitted = true);
  }

  void next() {
    if (index + 1 >= widget.checks.length) {
      Navigator.pop(context);
      return;
    }
    setState(() {
      index++;
      selected = null;
      submitted = false;
    });
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Knowledge check'),
    content: SingleChildScrollView(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(check.question, style: Theme.of(context).textTheme.titleMedium),
      const SizedBox(height: 12),
      DropdownButtonFormField<int>(
        initialValue: selected,
        decoration: const InputDecoration(labelText: 'Choose an answer'),
        items: List.generate(check.options.length, (option) => DropdownMenuItem(value: option, child: Text(check.options[option]))),
        onChanged: submitted ? null : (value) => setState(() => selected = value),
      ),
      if (submitted) ...[
        const SizedBox(height: 8),
        Text(
          selected == check.correctOption ? 'Correct' : 'Review this answer',
          style: TextStyle(fontWeight: FontWeight.bold, color: selected == check.correctOption ? Colors.green : Colors.orange),
        ),
        const SizedBox(height: 4),
        Text(check.explanation),
      ],
    ])),
    actions: [
      if (!submitted) FilledButton(onPressed: selected == null ? null : submit, child: const Text('Check answer')),
      if (submitted) FilledButton(onPressed: next, child: Text(index + 1 == widget.checks.length ? 'Done' : 'Next')),
    ],
  );
}
