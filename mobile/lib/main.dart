import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/auth_screen.dart';
import 'screens/home_screen.dart';
import 'services/api_service.dart';
import 'screens/deletion_status_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  final api = ApiService();
  try { await api.privacy.artifacts.initialise(); } catch (_) { /* Private operations remain gated until cleanup succeeds. */ }
  final signedIn = await api.restoreSession();
  runApp(ScamShieldApp(api: api, signedIn: signedIn));
}

class ScamShieldApp extends StatefulWidget {
  const ScamShieldApp({super.key, required this.api, required this.signedIn});
  final ApiService api;
  final bool signedIn;

  @override State<ScamShieldApp> createState() => _ScamShieldAppState();
}

class _ScamShieldAppState extends State<ScamShieldApp> {
  late bool authenticated;
  String? activeSessionId;
  int navigationEpoch = 0;
  late Future<void> artifactReady;
  @override void initState() {
    super.initState();
    authenticated = widget.signedIn;
    activeSessionId = widget.api.sessions.session?.sessionId;
    artifactReady = widget.api.privacy.artifacts.ready;
    widget.api.sessions.addListener(sessionChanged);
  }
  void sessionChanged() {
    final next = widget.api.sessions.isAuthenticated;
    final nextSessionId = widget.api.sessions.session?.sessionId;
    if (mounted) {
      setState(() {
        if (next != authenticated || nextSessionId != activeSessionId) {
          navigationEpoch++;
          artifactReady = widget.api.privacy.artifacts.ready;
        }
        authenticated = next;
        activeSessionId = nextSessionId;
      });
    }
  }
  @override void dispose() { widget.api.sessions.removeListener(sessionChanged); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      // A new navigation tree disposes every account-private route and screen state.
      key: ValueKey((authenticated, activeSessionId, navigationEpoch)),
      title: 'ScamShield',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff3568e8), brightness: Brightness.light),
        scaffoldBackgroundColor: const Color(0xfff6f8fc),
        navigationBarTheme: const NavigationBarThemeData(height: 72),
        inputDecorationTheme: InputDecorationTheme(
          filled: true, fillColor: Colors.white,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: const BorderSide(color: Color(0xff3568e8), width: 1.5)),
          contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        ),
      ),
      darkTheme: ThemeData(
        useMaterial3: true,
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff7da2ff), brightness: Brightness.dark),
        navigationBarTheme: const NavigationBarThemeData(height: 72),
        inputDecorationTheme: InputDecorationTheme(filled: true, border: OutlineInputBorder(borderRadius: BorderRadius.circular(16), borderSide: BorderSide.none), contentPadding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16)),
      ),
      themeMode: ThemeMode.system,
      home: authenticated ? FutureBuilder<void>(future: artifactReady, builder: (context, snapshot) {
        if (snapshot.hasError) {
          return Scaffold(body: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('Private cleanup needs a retry before opening this account.'),
            FilledButton(onPressed: () async {
              try { await widget.api.privacy.artifacts.initialise(); } catch (_) { /* Keep the gate closed. */ }
              if (mounted) setState(() => artifactReady = widget.api.privacy.artifacts.ready);
            }, child: const Text('Retry private cleanup')),
          ])));
        }
        if (snapshot.connectionState != ConnectionState.done) return const Scaffold(body: Center(child: CircularProgressIndicator()));
        return HomeScreen(api: widget.api);
      }) : Scaffold(body: Column(children: [
        Expanded(child: AuthScreen(api: widget.api)),
        Builder(builder: (context) => TextButton(onPressed: () => Navigator.push(context,
          MaterialPageRoute(builder: (_) => DeletionStatusScreen(privacy: widget.api.privacy))),
          child: const Text('Account-deletion status'))),
      ])),
    );
  }
}
