import 'package:flutter/material.dart';

import '../models/catalog.dart';
import '../services/api_service.dart';

class EmergencyScreen extends StatefulWidget {
  const EmergencyScreen({super.key, required this.api, this.language = 'en'});
  final ApiService api;
  final String language;
  @override State<EmergencyScreen> createState() => _EmergencyScreenState();
}

class _EmergencyScreenState extends State<EmergencyScreen> {
  late Future<List<EmergencyPlaybook>> future;
  @override void initState() { super.initState(); future = widget.api.catalog.emergencyPlaybooks(language: widget.language); }
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Urgent guidance')), body: FutureBuilder<List<EmergencyPlaybook>>(future: future, builder: (context, snapshot) {
    if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
    if (snapshot.hasError) return const Center(child: Padding(padding: EdgeInsets.all(24), child: Text('Emergency guidance could not be loaded. Try again from the guest home screen.')));
    final items = snapshot.data ?? const <EmergencyPlaybook>[];
    return ListView(padding: const EdgeInsets.all(20), children: [
      Card(color: Theme.of(context).colorScheme.errorContainer, elevation: 0, child: const Padding(padding: EdgeInsets.all(16), child: Text('This guidance is available to guests and includes bundled offline content. It does not replace emergency services or provider support.'))),
      if (widget.api.catalog.lastResponseWasFallback) const Card(elevation: 0, child: Padding(padding: EdgeInsets.all(14), child: Text('Showing the last known-good or bundled emergency guidance because the service is unavailable.'))),
      const SizedBox(height: 12), ...items.map((item) => Card(child: ListTile(title: Text(item.title), subtitle: Text(item.summary), onTap: () => _open(context, item)))),
    ]);
  }));

  void _open(BuildContext context, EmergencyPlaybook playbook) => Navigator.push(context, MaterialPageRoute(builder: (_) => Scaffold(
    appBar: AppBar(title: const Text('Immediate steps')), body: ListView(padding: const EdgeInsets.all(20), children: [
      Text(playbook.title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)), const SizedBox(height: 8), Text(playbook.summary),
      if (playbook.reviewStatus != 'reviewed') const Card(elevation: 0, child: Padding(padding: EdgeInsets.all(14), child: Text('Draft guidance — editorial review is pending. Verify important requests independently.'))),
      const SizedBox(height: 12), _section(context, 'Do this now', playbook.immediateActions), _section(context, 'Preserve evidence', playbook.preserveEvidence),
      _section(context, 'Recovery', playbook.recoveryActions), _section(context, 'Escalation and support', playbook.escalationGuidance),
    ]))));
  Widget _section(BuildContext context, String title, List<String> values) => Padding(padding: const EdgeInsets.only(top: 18), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(title, style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)), const SizedBox(height: 8),
    ...values.map((value) => Padding(padding: const EdgeInsets.only(bottom: 8), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Text('•  '), Expanded(child: Text(value))]))),
  ]));
}
