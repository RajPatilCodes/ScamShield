import 'package:flutter/material.dart';

import '../models/catalog.dart';

class GuideDetailScreen extends StatelessWidget {
  const GuideDetailScreen({super.key, required this.guide});
  final CatalogGuide guide;
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: Text(guide.id)), body: ListView(padding: const EdgeInsets.all(20), children: [
    if (guide.language.fallback) _notice(context, 'Hindi content is not available for this guide yet. Showing English text.'),
    _notice(context, 'Draft guidance — editorial review is pending. Verify important requests independently.'),
    Text(guide.title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
    const SizedBox(height: 8), Text(guide.summary), const SizedBox(height: 20),
    _section(context, 'What this can look like', [guide.scenario]), _section(context, 'Warning signs', guide.warningSigns),
    _section(context, 'Safer actions', guide.safeActions), _section(context, 'If you may be affected', guide.recoveryGuidance),
    _section(context, 'Reporting and records', guide.reportingGuidance), _section(context, 'Prevention', guide.preventionTips),
    _section(context, 'Keep context in mind', guide.falsePositiveNotes),
    const SizedBox(height: 12), Text('Content version ${guide.contentVersion}', style: Theme.of(context).textTheme.bodySmall),
  ]));
  Widget _notice(BuildContext context, String text) => Card(color: Theme.of(context).colorScheme.secondaryContainer, elevation: 0, child: Padding(padding: const EdgeInsets.all(14), child: Text(text)));
  Widget _section(BuildContext context, String title, List<String> values) => Padding(padding: const EdgeInsets.only(top: 18), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)), const SizedBox(height: 8),
    ...values.map((value) => Padding(padding: const EdgeInsets.only(bottom: 8), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Text('•  '), Expanded(child: Text(value))]))),
  ]));
}
