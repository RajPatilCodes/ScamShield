import 'package:flutter/material.dart';
import '../models/privacy.dart';
import '../services/privacy_service.dart';
import 'recent_auth_screen.dart';
import 'deletion_status_screen.dart';

class PrivacyScreen extends StatefulWidget {
  const PrivacyScreen({super.key, required this.privacy});
  final PrivacyService privacy;
  @override State<PrivacyScreen> createState() => _PrivacyScreenState();
}

class _PrivacyScreenState extends State<PrivacyScreen> {
  PrivacySettings? settings;
  List<PrivacyJob> jobs = [];
  List<PrivacyJob> deletions = [];
  bool busy = true;
  String? message;
  @override void initState() { super.initState(); load(); }
  Future<void> load() => operate(() async {
    final next = await widget.privacy.settings();
    final exports = await widget.privacy.exports();
    final statuses = <PrivacyJob>[];
    for (final deletion in deletions) { statuses.add(await widget.privacy.deletionStatus(deletion.id)); }
    if (mounted) setState(() { settings = next; jobs = exports; deletions = statuses; });
  });
  Future<void> operate(Future<void> Function() action) async {
    if (mounted) setState(() { busy = true; message = null; });
    try { await action(); }
    catch (error) { if (mounted) setState(() => message = error is PrivacyException ? error.message : 'The privacy operation could not be confirmed.'); }
    if (mounted) setState(() => busy = false);
  }
  Future<String?> reauth(String action, {String target = 'self'}) => Navigator.push<String>(context,
    MaterialPageRoute(builder: (_) => RecentAuthScreen(privacy: widget.privacy, action: action, target: target)));
  Future<bool> confirm(String title, String text) async => await showDialog<bool>(context: context,
    builder: (context) => AlertDialog(title: Text(title), content: Text(text), actions: [
      TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
      FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Confirm')),
    ])) ?? false;
  Future<void> changeConsent(bool enabled) async {
    if (enabled && !await confirm('Product saving choice', settings!.notice)) return;
    await operate(() async { await widget.privacy.consent(settings!, enabled); settings = await widget.privacy.settings(); });
  }
  Future<void> export() async {
    final grant = await reauth('export_create');
    if (grant == null) return;
    await operate(() async { await widget.privacy.createExport(grant); jobs = await widget.privacy.exports(); });
  }
  Future<void> download(PrivacyJob job) async {
    final grant = await reauth('export_download', target: job.id);
    if (grant == null) return;
    await operate(() async {
      final captured = widget.privacy.context;
      final file = await widget.privacy.download(job, grant);
      final saved = await widget.privacy.artifacts.saveUserCopy(captured, file, maxBytes: widget.privacy.exportMaxBytes);
      if (mounted) setState(() => message = saved ? 'Copy saved to your chosen location. That copy is outside later app cleanup.' : 'File saving cancelled. The app-managed copy is temporary.');
    });
  }
  Future<void> deleteSaved() async {
    if (!await confirm('Delete saved checks?', 'Saved checks disappear immediately. Physical purge may retry. New saving still requires current consent and an explicit scan choice.')) return;
    final grant = await reauth('delete_saved');
    if (grant == null) return;
    await operate(() async {
      final job = await widget.privacy.deleteSaved(grant);
      deletions = [job, ...deletions.where((previous) => previous.id != job.id)];
      message = 'Saved-data deletion: ${job.state}';
    });
  }
  Future<void> deleteAccount() async {
    if (!await confirm('Delete account?', 'This immediately restricts your account and revokes sessions. There is no cancellation period. Failed purge remains retryable.')) return;
    final grant = await reauth('delete_account');
    if (grant == null) return;
    await operate(() async { await widget.privacy.deleteAccount(grant); });
  }
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Privacy and data')),
    body: ListView(padding: const EdgeInsets.all(24), children: [
      const Text('Product data controls — not a legal privacy notice.'),
      if (settings != null) ...[
        Text(settings!.notice),
        SwitchListTile(title: const Text('Allow saved text checks'), subtitle: const Text('Each scan still requires an explicit saving choice.'),
          value: settings!.savingEnabled, onChanged: busy ? null : changeConsent),
      ],
      if (busy) const Center(child: CircularProgressIndicator()),
      if (message != null) Semantics(liveRegion: true, child: Text(message!)),
      OutlinedButton(onPressed: busy ? null : load, child: const Text('Refresh controls and exports')),
      FilledButton(onPressed: busy ? null : export, child: const Text('Request JSONL export')),
      for (final job in jobs) ListTile(title: Text('Export: ${job.state}'), subtitle: Text(job.errorCode ?? 'Temporary staging: 24 hours'),
        trailing: job.state == 'ready' ? IconButton(tooltip: 'Download and save export', onPressed: busy ? null : () => download(job), icon: const Icon(Icons.download)) : null),
      OutlinedButton(onPressed: busy ? null : deleteSaved, child: const Text('Delete all saved checks')),
      for (final job in deletions) ListTile(title: Text('Saved-data deletion: ${job.state}'),
        subtitle: Text(job.state == 'completed' ? 'Physical purge completed.' : job.state == 'failed'
          ? 'Physical purge needs a maintenance retry. Data stays logically deleted.' : 'Physical purge is pending or retrying.')),
      OutlinedButton(onPressed: busy ? null : deleteAccount, child: const Text('Delete account')),
      TextButton(onPressed: () => Navigator.push(context, MaterialPageRoute(builder: (_) => DeletionStatusScreen(privacy: widget.privacy))),
        child: const Text('Protected account-deletion status')),
    ]));
}
