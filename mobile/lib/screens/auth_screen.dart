import 'package:flutter/material.dart';
import '../services/api_service.dart';
import 'verify_email_screen.dart';
import 'password_recovery_screen.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key, required this.api});
  final ApiService api;
  @override State<AuthScreen> createState() => _AuthScreenState();
}
class _AuthScreenState extends State<AuthScreen> {
  final email = TextEditingController(); final password = TextEditingController();
  bool register = false, loading = false;
  String? error;
  @override
  void dispose() { email.dispose(); password.dispose(); super.dispose(); }
  Future<void> submit() async {
    setState(() { loading = true; error = null; });
    try {
      final success = await widget.api.authenticate(email.text, password.text, register: register);
      password.clear();
      if (register) {
        if (!mounted) return;
        await Navigator.of(context).push(MaterialPageRoute(builder: (_) => VerifyEmailScreen(api: widget.api, email: email.text)));
        if (mounted) setState(() => register = false);
        return;
      }
      if (!success) throw const MediaScanException('Sign in failed. Please try again.');
      if (!mounted) return;
    } catch (e) {
      password.clear();
      if (mounted) setState(() => error = e is MediaScanException ? e.message : 'Unable to sign in. Please try again.');
    } finally { if (mounted) setState(() => loading = false); }
  }
  @override Widget build(BuildContext context) => Scaffold(body: SafeArea(child: Center(child: SingleChildScrollView(padding: const EdgeInsets.all(28), child: ConstrainedBox(constraints: const BoxConstraints(maxWidth: 440), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
    Container(width: 56, height: 56, decoration: BoxDecoration(color: const Color(0xffe6edff), borderRadius: BorderRadius.circular(18)), child: const Icon(Icons.shield_rounded, color: Color(0xff3568e8), size: 32)),
    const SizedBox(height: 28), Text(register ? 'Create your shield' : 'Welcome to ScamShield', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold)), const SizedBox(height: 8), Text(register ? 'Stay one step ahead of suspicious messages.' : 'Spot scams before they reach your wallet.', style: TextStyle(color: Colors.grey.shade600)), const SizedBox(height: 34),
    TextField(controller: email, keyboardType: TextInputType.emailAddress, decoration: const InputDecoration(labelText: 'Email address', prefixIcon: Icon(Icons.email_outlined))), const SizedBox(height: 14), TextField(controller: password, obscureText: true, autocorrect: false, enableSuggestions: false, decoration: const InputDecoration(labelText: 'Password', prefixIcon: Icon(Icons.lock_outline))), const SizedBox(height: 22),
    if (widget.api.sessions.notice != null) Padding(padding: const EdgeInsets.only(bottom: 16), child: Semantics(liveRegion: true, child: Text(widget.api.sessions.notice!))),
    if (error != null) Padding(padding: const EdgeInsets.only(bottom: 16), child: Semantics(liveRegion: true, child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)))),
    TextButton(onPressed: loading ? null : () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => PasswordRecoveryScreen(api: widget.api))), child: const Text('Forgot password?')),
    TextButton(onPressed: loading ? null : () => Navigator.of(context).push(MaterialPageRoute(builder: (_) => VerifyEmailScreen(api: widget.api, email: email.text))), child: const Text('Verify email')),
    SizedBox(width: double.infinity, child: FilledButton(onPressed: loading ? null : submit, style: FilledButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 17)), child: loading ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white)) : Text(register ? 'Create account' : 'Sign in'))), const SizedBox(height: 18), Center(child: TextButton(onPressed: loading ? null : () => setState(() { register = !register; error = null; }), child: Text(register ? 'Already have an account? Sign in' : 'New to ScamShield? Create account')))
  ]))))));
}
