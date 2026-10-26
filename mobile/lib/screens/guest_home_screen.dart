import 'package:flutter/material.dart';

import '../services/api_service.dart';
import 'auth_screen.dart';
import 'catalog_screen.dart';
import 'checklist_screen.dart';
import 'emergency_screen.dart';
import 'learning_screen.dart';
import 'resource_directory_screen.dart';
import 'deletion_status_screen.dart';

class GuestHomeScreen extends StatefulWidget {
  const GuestHomeScreen({super.key, required this.api});
  final ApiService api;
  @override State<GuestHomeScreen> createState() => _GuestHomeScreenState();
}

class _GuestHomeScreenState extends State<GuestHomeScreen> {
  String language = 'en';
  void open(Widget screen) => Navigator.push(context, MaterialPageRoute(builder: (_) => screen));

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('ScamShield'), actions: [
      Padding(padding: const EdgeInsets.only(right: 12), child: DropdownButton<String>(value: language, underline: const SizedBox(),
        onChanged: (value) => setState(() => language = value ?? 'en'), items: const [DropdownMenuItem(value: 'en', child: Text('English')), DropdownMenuItem(value: 'hi', child: Text('हिन्दी'))])),
    ]),
    body: ListView(padding: const EdgeInsets.all(20), children: [
      Text('Stay one step ahead.', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
      const SizedBox(height: 8),
      const Text('Welcome to ScamShield'),
      const SizedBox(height: 8),
      const Text('Browse practical scam guidance without signing in. Emergency guidance is available offline.'),
      TextButton(onPressed: () => open(AuthScreen(api: widget.api, initialRegister: true)), child: const Text('New to ScamShield? Create account')),
      const SizedBox(height: 20),
      Card(color: Theme.of(context).colorScheme.errorContainer, elevation: 0, child: ListTile(contentPadding: const EdgeInsets.all(18),
        leading: const Icon(Icons.warning_amber_rounded, size: 34), title: const Text('Need urgent help?'),
        subtitle: const Text('Open immediate steps for a payment, account, or access warning.'),
        onTap: () => open(EmergencyScreen(api: widget.api, language: language)))),
      const SizedBox(height: 12),
      Card(child: ListTile(leading: const Icon(Icons.menu_book_outlined), title: const Text('Scam guide catalog'),
        subtitle: const Text('Browse all 33 scenario guides.'), onTap: () => open(CatalogScreen(api: widget.api, language: language)))),
      Card(child: ListTile(leading: const Icon(Icons.school_outlined), title: const Text('Learn the basics'),
        subtitle: const Text('Short lessons for safer decisions.'), onTap: () => open(LearningScreen(api: widget.api, language: language)))),
      Card(child: ListTile(leading: const Icon(Icons.checklist_outlined), title: const Text('Checklists'),
        subtitle: const Text('Track small guest-only steps on this device.'), onTap: () => open(ChecklistScreen(api: widget.api, language: language)))),
      Card(child: ListTile(leading: const Icon(Icons.account_balance_outlined), title: const Text('Resource directory'),
        subtitle: const Text('Destinations remain clearly marked until independently verified.'), onTap: () => open(ResourceDirectoryScreen(api: widget.api, language: language)))),
      const SizedBox(height: 18),
      OutlinedButton.icon(onPressed: () => open(AuthScreen(api: widget.api)), icon: const Icon(Icons.login), label: const Text('Sign in for private scans')),
      TextButton(onPressed: () => open(DeletionStatusScreen(privacy: widget.api.privacy)), child: const Text('Account-deletion status')),
      const SizedBox(height: 18),
      const Text('Guest checklist progress stays local to this app. It is not uploaded or linked to an account.', textAlign: TextAlign.center),
    ]),
  );
}
