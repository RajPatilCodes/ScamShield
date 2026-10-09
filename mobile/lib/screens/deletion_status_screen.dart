import 'package:flutter/material.dart';
import '../models/privacy.dart';
import '../services/privacy_service.dart';

class DeletionStatusScreen extends StatefulWidget {
  const DeletionStatusScreen({super.key, required this.privacy});
  final PrivacyService privacy;
  @override State<DeletionStatusScreen> createState() => _DeletionStatusScreenState();
}

class _DeletionStatusScreenState extends State<DeletionStatusScreen> {
  PrivacyJob? job;
  bool loading = true;
  String? error;
  @override void initState() { super.initState(); load(); }
  Future<void> load() async {
    setState(() { loading = true; error = null; });
    try { final next = await widget.privacy.receiptStatus(); if (mounted) setState(() => job = next); }
    catch (_) { if (mounted) setState(() => error = 'Status could not be confirmed. This does not mean deletion completed.'); }
    if (mounted) setState(() => loading = false);
  }
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Account deletion status')),
    body: ListView(padding: const EdgeInsets.all(24), children: [
      if (loading) const Center(child: CircularProgressIndicator())
      else if (error != null) Semantics(liveRegion: true, child: Text(error!))
      else if (job == null) const Text('No protected deletion receipt is stored for this API.')
      else ...[
        Text('Status: ${job!.state}'),
        Text(job!.state == 'completed' ? 'Application-data purge completed. Approved minimal audit/lifecycle records have their own retention.'
          : job!.state == 'failed' ? 'Deletion needs a maintenance retry. The account remains restricted.'
          : 'The account is restricted. Physical deletion is pending or being retried.'),
      ],
      const SizedBox(height: 16),
      OutlinedButton(onPressed: loading ? null : load, child: const Text('Refresh status')),
    ]));
}
