import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'screens/auth_screen.dart';
import 'screens/home_screen.dart';
import 'services/api_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  final api = ApiService();
  final signedIn = await api.isSignedIn();
  runApp(ScamShieldApp(api: api, signedIn: signedIn));
}

class ScamShieldApp extends StatelessWidget {
  const ScamShieldApp({super.key, required this.api, required this.signedIn});
  final ApiService api;
  final bool signedIn;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
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
      home: signedIn ? HomeScreen(api: api) : AuthScreen(api: api),
    );
  }
}
