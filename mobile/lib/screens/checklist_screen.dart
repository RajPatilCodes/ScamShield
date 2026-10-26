import 'package:flutter/material.dart';

import '../models/catalog.dart';
import '../services/api_service.dart';

class ChecklistScreen extends StatefulWidget {
  const ChecklistScreen({super.key, required this.api, this.language = 'en'});
  final ApiService api;
  final String language;
  @override
  State<ChecklistScreen> createState() => _ChecklistScreenState();
}

class _ChecklistScreenState extends State<ChecklistScreen> {
  late Future<List<LearningChecklist>> future;
  final completed = <String>{};

  @override
  void initState() {
    super.initState();
    future = _load();
  }

  Future<List<LearningChecklist>> _load() async {
    final values = await widget.api.catalog.checklists(language: widget.language);
    final loaded = <String>{};
    for (final checklist in values) {
      for (final item in checklist.items) {
        if (await widget.api.catalog.progress.contains('${checklist.id}:${item.id}')) {
          loaded.add('${checklist.id}:${item.id}');
        }
      }
    }
    if (mounted) {
      setState(() {
        completed
          ..clear()
          ..addAll(loaded);
      });
    }
    return values;
  }

  Future<void> toggle(String id, bool value) async {
    setState(() {
      if (value) {
        completed.add(id);
      } else {
        completed.remove(id);
      }
    });
    await widget.api.catalog.setGuestProgress(id, value, language: widget.language);
  }

  Future<void> resetProgress() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reset guest progress?'),
        content: const Text('This clears checklist progress stored on this device. It is not uploaded or recoverable from an account.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Reset')),
        ],
      ),
    );
    if (confirmed != true) return;
    await widget.api.catalog.progress.clear();
    if (mounted) setState(completed.clear);
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Checklists'),
      actions: [IconButton(onPressed: resetProgress, tooltip: 'Reset guest progress', icon: const Icon(Icons.delete_outline))],
    ),
    body: FutureBuilder<List<LearningChecklist>>(
      future: future,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
        if (snapshot.hasError) return _error();
        final values = snapshot.data ?? const <LearningChecklist>[];
        return ListView(padding: const EdgeInsets.all(20), children: [
          const Text('Progress is stored only on this device while you are a guest.'),
          const SizedBox(height: 12),
          if (widget.api.catalog.lastResponseWasFallback) const Card(
            elevation: 0,
            child: Padding(padding: EdgeInsets.all(14), child: Text('Showing the last known-good public content. It may be out of date.')),
          ),
          ...values.map((checklist) => Card(child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              ListTile(title: Text(checklist.title), subtitle: Text(checklist.summary)),
              ...checklist.items.map((item) {
                final id = '${checklist.id}:${item.id}';
                return CheckboxListTile(
                  value: completed.contains(id),
                  onChanged: (value) => toggle(id, value ?? false),
                  title: Text(item.label),
                );
              }),
            ]),
          ))),
        ]);
      },
    ),
  );

  Widget _error() => Center(child: Padding(
    padding: const EdgeInsets.all(28),
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      const Icon(Icons.cloud_off, size: 44),
      const SizedBox(height: 12),
      const Text('Checklists are unavailable right now.'),
      TextButton(onPressed: () => setState(() => future = _load()), child: const Text('Try again')),
    ]),
  ));
}
