import 'package:flutter/material.dart';
import '../services/api_service.dart';

class VerifyEmailScreen extends StatefulWidget {
  const VerifyEmailScreen({super.key, required this.api, required this.email});
  final ApiService api;
  final String email;
  @override State<VerifyEmailScreen> createState() => _VerifyEmailScreenState();
}

class _VerifyEmailScreenState extends State<VerifyEmailScreen> {
  final token = TextEditingController();
  late final email = TextEditingController(text: widget.email);
  bool loading = false;
  String? message;
  @override void dispose() { token.clear(); token.dispose(); email.dispose(); super.dispose(); }
  Future<void> run(bool confirm) async {
    setState(() { loading = true; message = null; });
    try {
      if (confirm) {
        await widget.api.verifyEmail(token.text);
        token.clear();
        if (mounted) setState(() => message = 'Email verified. Return to sign in.');
      } else {
        await widget.api.requestVerification(email.text);
        if (mounted) setState(() => message = 'If eligible, check your email for further instructions.');
      }
    } catch (error) {
      if (mounted) setState(() => message = error is MediaScanException ? error.message : 'Verification unavailable. Please try again.');
    } finally { if (mounted) setState(() => loading = false); }
  }
  @override Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Verify email')),
    body: ListView(padding: const EdgeInsets.all(24), children: [
      TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email address')),
      TextButton(onPressed: loading ? null : () => run(false), child: const Text('Request verification email')),
      TextField(controller: token, obscureText: true, autocorrect: false, enableSuggestions: false, decoration: const InputDecoration(labelText: 'Verification credential')),
      FilledButton(onPressed: loading ? null : () => run(true), child: const Text('Confirm email')),
      if (message != null) Semantics(liveRegion: true, child: Text(message!)),
    ]),
  );
}
