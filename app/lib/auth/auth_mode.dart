/// Loopback/emulator hosts a local or CI backend can legitimately run on.
/// `10.0.2.2` is the Android emulator's alias for the host machine's
/// `localhost`.
const Set<String> _nonProductionHosts = <String>{
  'localhost',
  '127.0.0.1',
  '10.0.2.2',
  '::1',
};

/// Is [apiBaseUrl] a production backend? Fails safe: anything unparseable or not a recognised
/// local/loopback host counts as production, so the e2e entrypoint refuses any real deployed backend.
bool isProductionApiBaseUrl(String apiBaseUrl) {
  final Uri? uri = Uri.tryParse(apiBaseUrl);
  if (uri == null || uri.host.isEmpty) return true;
  return !_nonProductionHosts.contains(uri.host.toLowerCase());
}
