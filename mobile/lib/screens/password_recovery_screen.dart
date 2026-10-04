import 'package:flutter/material.dart';
import '../services/api_service.dart';

class PasswordRecoveryScreen extends StatefulWidget {
  const PasswordRecoveryScreen({super.key, required this.api});
  final ApiService api;
  @override State<PasswordRecoveryScreen> createState() => _PasswordRecoveryScreenState();
}

class _PasswordRecoveryScreenState extends State<PasswordRecoveryScreen> {
  final email = TextEditingController();
  final token = TextEditingController();
  final password = TextEditingController();
  bool loading = false;
  String? message;
  @override void dispose() { email.dispose(); token.clear(); token.dispose(); password.clear(); password.dispose(); super.dispose(); }
  Future<void> run(bool confirm) async {
    setState(() { loading = true; message = null; });
    try {
      if (confirm) {
        await widget.api.recoverPassword(token.text, password.text);
        token.clear();
        password.clear();
        if (mounted) setState(() => message = 'Password replaced. Sign in with your new password.');
      } else {
        await widget.api.requestRecovery(email.text);
        if (mounted) setState(() => message = 'If eligible, check your email for further instructions.');
      }
    } catch (error) {
      password.clear();
      if (mounted) setState(() => message = error is MediaScanException ? error.message : 'Recovery unavailable. Please try again.');
    } finally { if (mounted) setState(() => loading = false); }
  }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Password recovery')),
    body: ListView(padding: const EdgeInsets.all(24), children: [
      TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email address')),
      TextButton(onPressed: loading ? null : () => run(false), child: const Text('Request recovery email')),
      TextField(controller: token, obscureText: true, autocorrect: false, enableSuggestions: false, decoration: const InputDecoration(labelText: 'Recovery credential')),
      TextField(controller: password, obscureText: true, autocorrect: false, enableSuggestions: false, decoration: const InputDecoration(labelText: 'New password')),
      FilledButton(onPressed: loading ? null : () => run(true), child: const Text('Replace password')),
      if (message != null) Semantics(liveRegion: true, child: Text(message!)),
    ]),
  );
}
