import 'package:flutter/material.dart';

import '../models/catalog.dart';
import '../services/api_service.dart';

class ResourceDirectoryScreen extends StatefulWidget {
  const ResourceDirectoryScreen({super.key, required this.api, this.language = 'en'});
  final ApiService api;
  final String language;
  @override State<ResourceDirectoryScreen> createState() => _ResourceDirectoryScreenState();
}

class _ResourceDirectoryScreenState extends State<ResourceDirectoryScreen> {
  late Future<List<TrustedResource>> future;
  @override void initState() { super.initState(); future = widget.api.catalog.resources(language: widget.language); }
  @override
  Widget build(BuildContext context) => Scaffold(appBar: AppBar(title: const Text('Resource directory')), body: FutureBuilder<List<TrustedResource>>(future: future, builder: (context, snapshot) {
    if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
    if (snapshot.hasError) return const Center(child: Text('Resources are unavailable right now.'));
    final resources = snapshot.data ?? const <TrustedResource>[];
    return ListView(padding: const EdgeInsets.all(20), children: [
      const Text('Resources remain unverified until their sources and destinations have been independently checked.'), const SizedBox(height: 12),
      ...resources.map((resource) => Card(child: ListTile(leading: const Icon(Icons.info_outline), title: Text(resource.name),
        subtitle: Text(resource.destination == null ? 'Unverified • destination pending independent verification' : 'Unverified • ${resource.destination}')))),
    ]);
  }));
}
