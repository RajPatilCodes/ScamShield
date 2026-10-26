import 'package:flutter/material.dart';

import '../models/catalog.dart';
import '../services/api_service.dart';
import 'guide_detail_screen.dart';

class CatalogScreen extends StatefulWidget {
  const CatalogScreen({super.key, required this.api, this.language = 'en'});
  final ApiService api;
  final String language;
  @override
  State<CatalogScreen> createState() => _CatalogScreenState();
}

class _CatalogScreenState extends State<CatalogScreen> {
  final query = TextEditingController();
  late Future<List<CatalogGuide>> future;
  late Future<List<CatalogCategory>> categoriesFuture;
  String? categoryId;

  @override
  void initState() {
    super.initState();
    categoriesFuture = widget.api.catalog.categories(language: widget.language);
    future = _request();
  }

  @override
  void dispose() {
    query.dispose();
    super.dispose();
  }

  Future<List<CatalogGuide>> _request() {
    final value = query.text.trim();
    if (value.isNotEmpty) {
      return widget.api.catalog.search(value, language: widget.language, limit: 50, categoryId: categoryId);
    }
    return widget.api.catalog.guides(language: widget.language, limit: 50, categoryId: categoryId);
  }

  void search() => setState(() => future = _request());

  Future<void> refresh() async {
    final next = _request();
    setState(() {
      categoriesFuture = widget.api.catalog.categories(language: widget.language);
      future = next;
    });
    await next;
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Guide catalog')),
    body: Column(children: [
      Padding(
        padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
        child: TextField(
          controller: query,
          textInputAction: TextInputAction.search,
          onSubmitted: (_) => search(),
          decoration: InputDecoration(
            prefixIcon: const Icon(Icons.search),
            hintText: 'Search guides',
            suffixIcon: IconButton(onPressed: search, tooltip: 'Search', icon: const Icon(Icons.arrow_forward)),
          ),
        ),
      ),
      Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: FutureBuilder<List<CatalogCategory>>(
          future: categoriesFuture,
          builder: (context, snapshot) {
            final categories = snapshot.data ?? const <CatalogCategory>[];
            if (categories.isEmpty) return const SizedBox.shrink();
            return DropdownButtonFormField<String>(
              initialValue: categoryId ?? '',
              decoration: const InputDecoration(labelText: 'Category'),
              items: [
                const DropdownMenuItem(value: '', child: Text('All categories')),
                ...categories.map((category) => DropdownMenuItem(value: category.id, child: Text(category.title))),
              ],
              onChanged: (value) => setState(() {
                categoryId = value == null || value.isEmpty ? null : value;
                future = _request();
              }),
            );
          },
        ),
      ),
      const SizedBox(height: 8),
      Expanded(child: FutureBuilder<List<CatalogGuide>>(
        future: future,
        builder: (context, snapshot) {
          if (snapshot.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snapshot.hasError) return _error();
          final items = snapshot.data ?? const <CatalogGuide>[];
          return RefreshIndicator(
            onRefresh: refresh,
            child: ListView(
              padding: const EdgeInsets.all(12),
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                if (widget.api.catalog.lastResponseWasFallback) _fallbackNotice(context),
                if (items.isEmpty) const Padding(padding: EdgeInsets.all(28), child: Center(child: Text('No guides found.'))),
                ...items.map((guide) => Card(child: ListTile(
                  title: Text('${guide.id} · ${guide.title}'),
                  subtitle: Text(guide.summary),
                  isThreeLine: true,
                  trailing: guide.language.fallback
                      ? const Tooltip(message: 'English content is shown because Hindi is not available yet.', child: Icon(Icons.translate))
                      : null,
                  onTap: () => Navigator.push(context, MaterialPageRoute(builder: (_) => GuideDetailScreen(guide: guide))),
                ))),
              ],
            ),
          );
        },
      )),
    ]),
  );

  Widget _fallbackNotice(BuildContext context) => Card(
    color: Theme.of(context).colorScheme.secondaryContainer,
    elevation: 0,
    child: const Padding(
      padding: EdgeInsets.all(14),
      child: Text('Showing the last known-good public content. It may be out of date; verify important guidance independently.'),
    ),
  );

  Widget _error() => Center(child: Padding(
    padding: const EdgeInsets.all(28),
    child: Column(mainAxisSize: MainAxisSize.min, children: [
      const Icon(Icons.cloud_off, size: 44),
      const SizedBox(height: 12),
      const Text('Guides are unavailable right now.'),
      const SizedBox(height: 8),
      TextButton(onPressed: () => setState(() => future = _request()), child: const Text('Try again')),
      const SizedBox(height: 8),
      const Text('Emergency guidance remains available from the guest home screen.', textAlign: TextAlign.center),
    ]),
  ));
}
