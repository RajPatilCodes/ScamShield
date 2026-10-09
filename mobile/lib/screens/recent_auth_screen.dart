import 'package:flutter/material.dart';
import '../services/privacy_service.dart';

class RecentAuthScreen extends StatefulWidget {
  const RecentAuthScreen({super.key, required this.privacy, required this.action, this.target = 'self'});
  final PrivacyService privacy;
  final String action;
  final String target;
  @override State<RecentAuthScreen> createState() => _RecentAuthScreenState();
}

class _RecentAuthScreenState extends State<RecentAuthScreen> {
  final password = TextEditingController();
  bool busy = false;
  String? error;
  @override void dispose() { password.clear(); password.dispose(); super.dispose(); }
  Future<void> submit() async {
    setState(() { busy = true; error = null; });
    try {
      final grant = await widget.privacy.reauthenticate(password.text, widget.action, target: widget.target);
      password.clear();
      if (mounted) Navigator.pop(context, grant);
    } catch (_) { if (mounted) setState(() { busy = false; error = 'Authentication could not be confirmed. Please try again.'; }); }
  }
  @override Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Confirm it is you')),
    body: ListView(padding: const EdgeInsets.all(24), children: [
      const Text('Re-enter your password for this action. Confirmation is short-lived and can be used once.'),
      TextField(controller: password, obscureText: true, enableSuggestions: false, autocorrect: false,
        enabled: !busy, decoration: const InputDecoration(labelText: 'Password')),
      if (error != null) Semantics(liveRegion: true, child: Text(error!)),
      FilledButton(onPressed: busy ? null : submit, child: Text(busy ? 'Confirming…' : 'Confirm')),
    ]));
}
