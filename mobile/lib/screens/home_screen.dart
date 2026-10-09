import 'package:flutter/material.dart';
import '../models/scan_result.dart';
import '../services/api_service.dart';
import 'auth_screen.dart';
import 'result_screen.dart';
import 'scan_screen.dart';
import 'privacy_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.api});
  final ApiService api;
  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int tab = 0;
  List<ScanResult> scans = [];
  bool loading = true;
  String? error;
  String query = '';
  String filter = 'All';
  int _historyLoad = 0;
  @override
  void initState() {
    super.initState();
    widget.api.privacy.historyRevision.addListener(_invalidateHistory);
    _load();
  }
  void _invalidateHistory() {
    _historyLoad++;
    if (mounted) setState(() { scans = []; loading = false; error = null; });
  }
  @override
  void dispose() {
    widget.api.privacy.historyRevision.removeListener(_invalidateHistory);
    super.dispose();
  }
  Future<void> _load() async {
    final load = ++_historyLoad;
    setState(() { loading = true; error = null; });
    try {
      final data = await widget.api.history();
      if (mounted && load == _historyLoad) setState(() => scans = data);
    } catch (_) { if (mounted && load == _historyLoad) setState(() => error = 'Unable to load history. Please try again.'); }
    if (mounted && load == _historyLoad) setState(() => loading = false);
  }
  Future<void> _scan() async {
    final result = await Navigator.push<ScanResult>(context, MaterialPageRoute(builder: (_) => ScanScreen(api: widget.api)));
    if (result != null && mounted) {
      if (result.isSaved || result.isMedia) setState(() => scans = [result, ...scans]);
      await Navigator.push(context, MaterialPageRoute(builder: (_) => ResultScreen(result: result, api: widget.api)));
      if (result.isSaved && mounted) await _load();
    }
  }
  Future<void> _logout() async {
    await widget.api.signOut();
    if (mounted) Navigator.pushAndRemoveUntil(context, MaterialPageRoute(builder: (_) => AuthScreen(api: widget.api)), (_) => false);
  }
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('ScamShield'), actions: [if (tab == 2) IconButton(onPressed: _load, tooltip: 'Refresh history', icon: const Icon(Icons.refresh))]),
    body: SafeArea(top: false, child: IndexedStack(index: tab, children: [_dashboard(), _scanTab(), _history(), _profile()])),
    bottomNavigationBar: NavigationBar(selectedIndex: tab, onDestinationSelected: (value) => setState(() => tab = value), destinations: const [
      NavigationDestination(icon: Icon(Icons.grid_view_rounded), label: 'Dashboard'),
      NavigationDestination(icon: Icon(Icons.document_scanner_outlined), label: 'Scan'),
      NavigationDestination(icon: Icon(Icons.history_rounded), label: 'History'),
      NavigationDestination(icon: Icon(Icons.person_outline), label: 'Profile'),
    ]),
  );
  Widget _dashboard() => RefreshIndicator(onRefresh: _load, child: ListView(padding: const EdgeInsets.all(20), physics: const AlwaysScrollableScrollPhysics(), children: [
    Text('Stay one step ahead.', style: Theme.of(context).textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w800)),
    const SizedBox(height: 8),
    const Text('Check suspicious messages before you act.'),
    const SizedBox(height: 24),
    Card(color: Theme.of(context).colorScheme.primaryContainer, elevation: 0, child: const Padding(padding: EdgeInsets.all(24), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [Icon(Icons.verified_user_rounded, size: 44), SizedBox(height: 16), Text('Scan before you trust', style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)), SizedBox(height: 8), Text('Get clear guidance on suspicious messages, emails, and links.')]))),
    const SizedBox(height: 16),
    FilledButton.icon(onPressed: _scan, icon: const Icon(Icons.add), label: const Text('Start a new scan')),
    const SizedBox(height: 28),
    Text('Recent scans', style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 12),
    if (loading) const Center(child: CircularProgressIndicator()) else if (error != null) _error() else if (scans.isEmpty) _empty('No scans yet', 'Your recent checks will appear here.') else ...scans.take(3).map(_tile),
  ]));
  Widget _scanTab() => Center(child: Padding(padding: const EdgeInsets.all(28), child: Column(mainAxisSize: MainAxisSize.min, children: [
    Icon(Icons.radar_rounded, size: 72, color: Theme.of(context).colorScheme.primary),
    const SizedBox(height: 20),
    Text('Ready when you are', style: Theme.of(context).textTheme.headlineSmall),
    const SizedBox(height: 8),
    const Text('Check a message, URL, camera photo, image, or video for a closer look.', textAlign: TextAlign.center),
    const SizedBox(height: 24),
    FilledButton.icon(onPressed: _scan, icon: const Icon(Icons.search), label: const Text('Scan content')),
  ])));
  Widget _history() {
    final shown = scans.where((s) => s.content.toLowerCase().contains(query.toLowerCase()) && (filter == 'All' || (s.isMedia ? filter == 'Media' : (filter == 'High risk' ? s.score >= 70 : filter == 'Review' ? s.score >= 35 && s.score < 70 : filter == 'Low risk' && s.score < 35)))).toList();
    return ListView(padding: const EdgeInsets.all(20), children: [
      TextField(onChanged: (value) => setState(() => query = value), decoration: const InputDecoration(prefixIcon: Icon(Icons.search), hintText: 'Search scans')),
      const SizedBox(height: 12),
      Wrap(spacing: 8, children: ['All', 'High risk', 'Review', 'Low risk', 'Media'].map((value) => ChoiceChip(label: Text(value), selected: filter == value, onSelected: (_) => setState(() => filter = value))).toList()),
      const SizedBox(height: 16),
      if (loading) const Center(child: CircularProgressIndicator()) else if (error != null) _error() else if (shown.isEmpty) _empty('No scans found', 'Try a different filter or start a new scan.') else ...shown.map(_tile),
    ]);
  }
  Widget _profile() => ListView(padding: const EdgeInsets.all(24), children: [
    const CircleAvatar(radius: 40, child: Icon(Icons.person_outline, size: 40)),
    const SizedBox(height: 16),
    Text('Your ScamShield profile', textAlign: TextAlign.center, style: Theme.of(context).textTheme.titleLarge),
    const SizedBox(height: 28),
    const Card(child: ListTile(leading: Icon(Icons.dark_mode_outlined), title: Text('Appearance'), subtitle: Text('Matches your device theme'))),
    const SizedBox(height: 16),
    ListTile(leading: const Icon(Icons.privacy_tip_outlined), title: const Text('Privacy and data'),
      onTap: () async {
        await Navigator.push(context, MaterialPageRoute(builder: (_) => PrivacyScreen(privacy: widget.api.privacy)));
        if (mounted && widget.api.sessions.isAuthenticated) await _load();
      }),
    OutlinedButton.icon(onPressed: _logout, icon: const Icon(Icons.logout), label: const Text('Log out')),
  ]);
  Widget _tile(ScanResult item) {
    final color = item.isMedia ? Colors.orange : item.score >= 70 ? Colors.red : item.score >= 35 ? Colors.orange : Colors.green;
    return Card(elevation: 0, child: ListTile(
      onTap: () async {
        await Navigator.push(context, MaterialPageRoute(builder: (_) => ResultScreen(result: item, api: widget.api)));
        if (item.isSaved && mounted) await _load();
      },
      leading: CircleAvatar(backgroundColor: color.withValues(alpha: .14), child: Icon(item.isMedia || item.score >= 35 ? Icons.warning_rounded : Icons.check_rounded, color: color)),
      title: Text(item.content, maxLines: 1, overflow: TextOverflow.ellipsis), subtitle: Text(item.isMedia ? '${item.level} • Metadata only' : item.level), trailing: item.isMedia ? const Icon(Icons.attach_file) : Text('${item.score}/100'),
    ));
  }
  Widget _empty(String title, String message) => Padding(padding: const EdgeInsets.symmetric(vertical: 36), child: Column(children: [const Icon(Icons.inbox_outlined, size: 48), const SizedBox(height: 12), Text(title, style: const TextStyle(fontWeight: FontWeight.bold)), const SizedBox(height: 8), Text(message, textAlign: TextAlign.center)]));
  Widget _error() => Column(children: [const Icon(Icons.cloud_off, size: 40), Text(error!), TextButton(onPressed: _load, child: const Text('Try again'))]);
}
