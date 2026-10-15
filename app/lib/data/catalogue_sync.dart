import '../api/api_client.dart';
import '../api/api_exception.dart';
import 'repositories/catalogue_repository.dart';

/// Brings the local catalogue up to the backend's. Offline-tolerant by design: the app works from what it holds, so
/// a failed sync (no network, signed out, server error, unreadable response) changes nothing and is tried again
/// at the next start or resume.
class CatalogueSync {
  CatalogueSync({
    required this.api,
    required this.repository,
    DateTime Function()? now,
  }) : _now = now ?? DateTime.now;

  final GleanApiClient api;
  final CatalogueRepository repository;
  final DateTime Function() _now;
  Future<void>? _running;

  /// Syncs once. A call made while one is already running joins it rather than starting a second request.
  Future<void> sync() =>
      _running ??= _run().whenComplete(() => _running = null);

  Future<void> _run() async {
    try {
      final since = await repository.syncedVersion();
      final changes = await api.getCatalogue(since: since);
      await repository.applyChanges(changes, now: _now());
    } on ApiException {
      // Offline, signed out or a bad response: keep what we hold.
    }
  }
}
