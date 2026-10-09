import 'dart:io';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:image_picker/image_picker.dart';
import '../models/scan_result.dart';
import '../services/api_service.dart';

class ScanScreen extends StatefulWidget {
  const ScanScreen({super.key, required this.api, this.picker});
  final ApiService api;
  final ImagePicker? picker;
  @override
  State<ScanScreen> createState() => _ScanScreenState();
}

class _ScanScreenState extends State<ScanScreen> {
  final controller = TextEditingController();
  late final ImagePicker picker = widget.picker ?? ImagePicker();
  bool loading = false;
  bool picking = false;
  XFile? media;
  String? mediaName;
  bool video = false;
  String? error;
  bool save = false;
  Timer? _mediaExpiry;

  Future<void> _selectCopy(File copy, String name, bool isVideo) async {
    final captured = widget.api.privacy.context;
    final expiry = await widget.api.privacy.artifacts.checkUse(captured, copy.path, requireManaged: true);
    if (!mounted) return;
    _mediaExpiry?.cancel();
    setState(() { media = XFile(copy.path, name: name); mediaName = name; video = isVideo; });
    _mediaExpiry = Timer(DateTime.fromMillisecondsSinceEpoch(expiry!).difference(DateTime.now()), () {
      if (!mounted) return;
      _removeMedia(expired: true);
    });
  }
  void _removeMedia({bool expired = false}) {
    _mediaExpiry?.cancel();
    final selected = media;
    if (selected != null) {
      FileImage(File(selected.path)).evict();
      widget.api.privacy.artifacts.discardPickerCopy(selected.path).catchError((_) {});
    }
    setState(() { media = null; mediaName = null; error = expired ? 'Selected media expired. Please select it again.' : null; });
  }

  @override
  void initState() {
    super.initState();
    if (Platform.isAndroid) _recoverMedia();
  }

  Future<void> _recoverMedia() async {
    try {
      final captured = widget.api.privacy.context;
      final pickerExpiresAt = await widget.api.privacy.store.recoverPicker(captured, DateTime.now());
      final lost = await picker.retrieveLostData();
      if (!mounted || lost.isEmpty) return;
      widget.api.privacy.check(captured);
      if (pickerExpiresAt == null) {
        for (final file in lost.files ?? <XFile>[]) { await widget.api.privacy.artifacts.discardPickerCopy(file.path); }
        if (mounted) setState(() => error = 'Please select media again for this account.');
        return;
      }
      if (lost.exception != null) {
        setState(() => error = 'The selected media could not be recovered. Please select it again.');
      } else if (lost.files?.isNotEmpty == true) {
        final original = lost.files!.first;
        final copy = await widget.api.privacy.artifacts.adoptPickerCopy(captured, original.path, expiresAt: pickerExpiresAt);
        widget.api.privacy.check(captured);
        if (!mounted) return;
        await _selectCopy(copy, original.name, lost.type == RetrieveType.video);
      }
    } catch (_) {
      if (mounted) setState(() => error = 'Please select your media again.');
    }
  }

  @override
  void dispose() {
    _mediaExpiry?.cancel();
    final selected = media;
    if (selected != null) {
      FileImage(File(selected.path)).evict();
      widget.api.privacy.artifacts.discardPickerCopy(selected.path).catchError((_) {});
    }
    controller.dispose();
    super.dispose();
  }

  Future<void> _pick(ImageSource source, {bool isVideo = false}) async {
    setState(() { picking = true; error = null; });
    try {
      final captured = widget.api.privacy.context;
      final pickerExpiresAt = await widget.api.privacy.store.beginPicker(captured, DateTime.now(), artifactHours: widget.api.privacy.artifactHours);
      final selected = isVideo
          ? await picker.pickVideo(source: source)
          : await picker.pickImage(source: source);
      if (selected != null && mounted) {
        widget.api.privacy.check(captured);
        if (DateTime.now().millisecondsSinceEpoch >= pickerExpiresAt) {
          await widget.api.privacy.store.clearPicker();
          await widget.api.privacy.artifacts.discardPickerCopy(selected.path);
          if (mounted) setState(() => error = 'Selected media expired. Please select it again.');
        } else if (await selected.length() > 20 * 1024 * 1024) {
          if (mounted) setState(() => error = 'Choose a file no larger than 20 MiB.');
        } else if (mounted) {
          final copy = await widget.api.privacy.artifacts.adoptPickerCopy(captured, selected.path, expiresAt: pickerExpiresAt);
          widget.api.privacy.check(captured);
          if (mounted) {
            await _selectCopy(copy, selected.name, isVideo);
            await widget.api.privacy.store.clearPicker();
          }
        }
      }
    } on PlatformException catch (e) {
      if (mounted) {
        setState(() => error = e.code.toLowerCase().contains('access') || e.code.toLowerCase().contains('denied')
          ? 'Camera or photo access was denied. Allow access in Android Settings, then try again.'
          : 'The camera or media picker is unavailable. Try selecting another file.');
      }
    } catch (_) {
      if (mounted) setState(() => error = 'Unable to open this media. Please choose another file.');
    } finally {
      if (mounted) setState(() => picking = false);
    }
  }

  Future<void> submit() async {
    if (media == null && controller.text.trim().isEmpty) {
      setState(() => error = 'Paste something or select media to scan first.');
      return;
    }
    setState(() { loading = true; error = null; });
    try {
      final result = media == null
          ? await widget.api.scan(controller.text.trim(), save: save)
          : await widget.api.scanMedia(media!, filename: mediaName);
      if (mounted) Navigator.pop<ScanResult>(context, result);
    } catch (e) {
      if (mounted) {
        setState(() {
        loading = false;
        error = e is MediaScanException ? e.message : 'The scan could not be completed. Please try again.';
        });
      }
    }
  }

  Future<void> savingChoice(bool value) async {
    if (!value) { setState(() => save = false); return; }
    setState(() => loading = true);
    try {
      final settings = await widget.api.privacy.settings();
      if (!mounted) return;
      if (!settings.savingEnabled) {
        final accepted = await showDialog<bool>(context: context, builder: (context) => AlertDialog(
          title: const Text('Product saving choice'), content: Text(settings.notice), actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Keep transient')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Allow saving'))]));
        if (accepted != true) return;
        await widget.api.privacy.consent(settings, true);
      }
      if (mounted) setState(() => save = true);
    } catch (_) { if (mounted) setState(() => error = 'Current saving consent could not be confirmed.'); }
    finally { if (mounted) setState(() => loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final busy = loading || picking;
    return Scaffold(
      appBar: AppBar(title: const Text('New scan')),
      body: ListView(padding: const EdgeInsets.all(20), children: [
        Text('Check suspicious content', style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold)),
        const SizedBox(height: 8),
        const Text('Paste a message or URL, take a photo, or choose an image or video.'),
        const SizedBox(height: 20),
        Wrap(spacing: 8, runSpacing: 8, children: [
          OutlinedButton.icon(onPressed: busy ? null : () => _pick(ImageSource.camera), icon: const Icon(Icons.camera_alt_outlined), label: const Text('Camera')),
          OutlinedButton.icon(onPressed: busy ? null : () => _pick(ImageSource.gallery), icon: const Icon(Icons.image_outlined), label: const Text('Image')),
          OutlinedButton.icon(onPressed: busy ? null : () => _pick(ImageSource.gallery, isVideo: true), icon: const Icon(Icons.video_library_outlined), label: const Text('Video')),
        ]),
        const SizedBox(height: 8),
        const Text('Media up to 20 MiB is uploaded for metadata-only screening. Camera photos are not read with OCR. No malware scan, image interpretation, or video content analysis is performed.'),
        const SizedBox(height: 16),
        if (media != null) Card(child: Column(children: [
          if (!video) ClipRRect(borderRadius: BorderRadius.circular(12), child: Image.file(File(media!.path), height: 180, fit: BoxFit.contain, errorBuilder: (_, __, ___) => const Padding(padding: EdgeInsets.all(24), child: Icon(Icons.image_not_supported_outlined, size: 48)))),
          ListTile(leading: Icon(video ? Icons.movie_outlined : Icons.image_outlined), title: Text(mediaName ?? media!.name, maxLines: 2, overflow: TextOverflow.ellipsis), subtitle: Text(video ? 'Video ready to scan' : 'Image ready to scan'), trailing: IconButton(tooltip: 'Remove media', onPressed: busy ? null : _removeMedia, icon: const Icon(Icons.close))),
        ])) else TextField(controller: controller, enabled: !busy, maxLines: 8, decoration: const InputDecoration(hintText: 'Paste a text message, email, or URL here...', alignLabelWithHint: true)),
        if (media == null) SwitchListTile(value: save, onChanged: busy ? null : savingChoice,
          title: const Text('Save this text check'), subtitle: const Text('Off by default. Requires current consent; expiry is shown on the saved result.')),
        if (error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Semantics(liveRegion: true, child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)))),
        const SizedBox(height: 18),
        FilledButton.icon(onPressed: busy ? null : submit, icon: busy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.search_rounded), label: Padding(padding: const EdgeInsets.symmetric(vertical: 15), child: Text(loading ? 'Analyzing...' : picking ? 'Opening media...' : 'Analyze now'))),
        const SizedBox(height: 18),
        const Card(elevation: 0, child: Padding(padding: EdgeInsets.all(16), child: Row(children: [Icon(Icons.info_outline), SizedBox(width: 12), Expanded(child: Text('A scan highlights warning signs. Always verify the source before sharing money or personal information.'))]))),
      ]),
    );
  }
}
