import 'package:flutter/material.dart';
import '../models/scan_result.dart';
import '../services/api_service.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({super.key, required this.result, this.api});
  final ScanResult result;
  final ApiService? api;
  @override
  Widget build(BuildContext context) {
    final color = result.isMedia ? Colors.orange : result.score >= 70 ? Colors.red : result.score >= 35 ? Colors.orange : Colors.green;
    return Scaffold(appBar: AppBar(title: const Text('Scan details')), body: SafeArea(top: false, child: ListView(padding: const EdgeInsets.all(20), children: [
      Card(color: color.withValues(alpha: .12), elevation: 0, child: Padding(padding: const EdgeInsets.all(28), child: Column(children: [
        Icon(result.isMedia || result.score >= 35 ? Icons.warning_amber_rounded : Icons.verified_user_outlined, color: color, size: 52),
        const SizedBox(height: 16),
        Text(result.isMedia ? 'Metadata only' : '${result.score}/100', style: Theme.of(context).textTheme.displaySmall?.copyWith(color: color, fontWeight: FontWeight.bold)),
        Text(result.level, style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        Text(result.isMedia ? 'Not malware scanned. Content remains unverified.' : 'Estimated risk • higher means more risk'),
      ]))),
      const SizedBox(height: 20),
      Text(result.isSaved ? 'Saved privately' : 'Session-only result — not saved to text history'),
      if (result.expiresAt != null) Text('Expires ${result.expiresAt!.toUtc()}'),
      if (result.provenance == 'legacy_no_retroactive_consent') const Text('Legacy saved check — no retroactive consent receipt.'),
      if (result.isSaved && api != null) OutlinedButton(onPressed: () async {
        final accepted = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
          title: const Text('Delete this saved check?'), content: const Text('It disappears immediately; physical purge follows.'),
          actions: [TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete'))]));
        if (accepted != true) return;
        try { await api!.privacy.deleteOne(result); if (context.mounted) Navigator.pop(context); }
        catch (_) { if (context.mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Deletion could not be confirmed. Please refresh.'))); }
      }, child: const Text('Delete saved check')),
      if (result.isMedia) ...[
        const Text('Only file metadata was screened. No OCR, image interpretation, video content analysis, or malware detection was performed.'),
        const SizedBox(height: 16),
        _section(context, 'File metadata', ['Type: ${result.contentType}', 'Size: ${result.sizeBytes} bytes']),
        const Text('SHA-256'),
        SelectableText(result.sha256!),
        const SizedBox(height: 20),
      ],
      _section(context, 'Signals detected', result.reasons.isEmpty ? ['No specific warning signals returned.'] : result.reasons),
      _section(context, 'What to do next', result.actions.isEmpty ? ['Verify the sender through a trusted channel before acting.'] : result.actions),
      Text('Original content', style: Theme.of(context).textTheme.titleLarge),
      const SizedBox(height: 8),
      Card(elevation: 0, child: Padding(padding: const EdgeInsets.all(16), child: SelectableText(result.content))),
      if (result.createdAt != null) Padding(padding: const EdgeInsets.symmetric(vertical: 12), child: Text('Scanned ${MaterialLocalizations.of(context).formatMediumDate(result.createdAt!.toLocal())}')),
      Text(result.isMedia ? 'This result cannot establish whether the file is safe. Verify the source before opening or sharing it.' : 'A low score does not guarantee safety. Pause and verify if something feels wrong.'),
      const SizedBox(height: 24),
      FilledButton(onPressed: () => Navigator.pop(context), child: const Text('Done')),
    ])));
  }
  Widget _section(BuildContext context, String title, List<String> items) => Padding(padding: const EdgeInsets.only(bottom: 24), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Text(title, style: Theme.of(context).textTheme.titleLarge), const SizedBox(height: 8),
    ...items.map((item) => Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [const Icon(Icons.chevron_right, size: 20), const SizedBox(width: 8), Expanded(child: Text(item))]))),
  ]));
}
