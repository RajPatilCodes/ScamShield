import 'dart:io';
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
  bool video = false;
  String? error;

  @override
  void initState() {
    super.initState();
    if (Platform.isAndroid) _recoverMedia();
  }

  Future<void> _recoverMedia() async {
    try {
      final lost = await picker.retrieveLostData();
      if (!mounted || lost.isEmpty) return;
      if (lost.exception != null) {
        setState(() => error = 'The selected media could not be recovered. Please select it again.');
      } else if (lost.files?.isNotEmpty == true) {
        setState(() {
          media = lost.files!.first;
          video = lost.type == RetrieveType.video;
        });
      }
    } on PlatformException {
      if (mounted) setState(() => error = 'Please select your media again.');
    }
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  Future<void> _pick(ImageSource source, {bool isVideo = false}) async {
    setState(() { picking = true; error = null; });
    try {
      final selected = isVideo
          ? await picker.pickVideo(source: source)
          : await picker.pickImage(source: source);
      if (selected != null && mounted) {
        if (await selected.length() > 20 * 1024 * 1024) {
          if (mounted) setState(() => error = 'Choose a file no larger than 20 MiB.');
        } else if (mounted) {
          setState(() { media = selected; video = isVideo; });
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
          ? await widget.api.scan(controller.text.trim())
          : await widget.api.scanMedia(media!);
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
          ListTile(leading: Icon(video ? Icons.movie_outlined : Icons.image_outlined), title: Text(media!.name, maxLines: 2, overflow: TextOverflow.ellipsis), subtitle: Text(video ? 'Video ready to scan' : 'Image ready to scan'), trailing: IconButton(tooltip: 'Remove media', onPressed: busy ? null : () => setState(() { media = null; error = null; }), icon: const Icon(Icons.close))),
        ])) else TextField(controller: controller, enabled: !busy, maxLines: 8, decoration: const InputDecoration(hintText: 'Paste a text message, email, or URL here...', alignLabelWithHint: true)),
        if (error != null) Padding(padding: const EdgeInsets.only(top: 12), child: Semantics(liveRegion: true, child: Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)))),
        const SizedBox(height: 18),
        FilledButton.icon(onPressed: busy ? null : submit, icon: busy ? const SizedBox(width: 18, height: 18, child: CircularProgressIndicator(strokeWidth: 2)) : const Icon(Icons.search_rounded), label: Padding(padding: const EdgeInsets.symmetric(vertical: 15), child: Text(loading ? 'Analyzing...' : picking ? 'Opening media...' : 'Analyze now'))),
        const SizedBox(height: 18),
        const Card(elevation: 0, child: Padding(padding: EdgeInsets.all(16), child: Row(children: [Icon(Icons.info_outline), SizedBox(width: 12), Expanded(child: Text('A scan highlights warning signs. Always verify the source before sharing money or personal information.'))]))),
      ]),
    );
  }
}
