import '../api/api_client.dart';
import '../api/api_exception.dart';
import 'repositories/catalogue_repository.dart';

/// How long a device goes on trusting delta syncs before it re-reads the whole catalogue. The backend reads items
/// through an eventually consistent index, so a delta can be told "version N" while missing an item written at or
/// before N; the item is never sent again unless it is rewritten. A full sync repairs that.
const Duration fullSyncInterval = Duration(hours: 24);

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

  // A stamp that is unreadable or in the future (the clock moved back) counts as due.
  bool _fullSyncDue(String lastFullSync, DateTime now) {
    final DateTime? last = DateTime.tryParse(lastFullSync);
    if (last == null) return true;
    final Duration age = now.difference(last);
    return age >= fullSyncInterval || age.isNegative;
  }

  Future<void> _run() async {
    try {
      final DateTime now = _now();
      final state = await repository.syncState();
      final bool full = state == null || _fullSyncDue(state.fullSyncedAt, now);
      final changes = await api.getCatalogue(since: full ? 0 : state.version);
      await repository.applyChanges(changes, now: now, fullSync: full);
    } on ApiException {
      // Offline, signed out or a bad response: keep what we hold.
    }
  }
}
