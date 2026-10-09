/// Loopback/emulator hosts a local or CI backend can legitimately run on.
/// `10.0.2.2` is the Android emulator's alias for the host machine's
/// `localhost`.
const Set<String> _nonProductionHosts = <String>{
  'localhost',
  '127.0.0.1',
  '10.0.2.2',
  '::1',
};

/// Is [apiBaseUrl] a production backend? Fails **safe**: anything that
/// doesn't parse, or whose host isn't a recognized local/loopback address,
/// counts as production. Deliberately broader than "matches our known prod
/// domain" — the e2e entrypoint must refuse to run against *any* real
/// deployed backend, staging included, not just a hardcoded production
/// hostname a future environment could rename.
bool isProductionApiBaseUrl(String apiBaseUrl) {
  final Uri? uri = Uri.tryParse(apiBaseUrl);
  if (uri == null || uri.host.isEmpty) return true;
  return !_nonProductionHosts.contains(uri.host.toLowerCase());
}
