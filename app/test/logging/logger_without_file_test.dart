// The web build has no filesystem: `path_provider` has no web implementation, so startup must not ask it for a
// storage directory. There the log is kept in memory (and mirrored to the browser console) instead.
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/logging/logging.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'a logger without a filesystem never asks for a storage directory',
    () async {
      // This test host has no path_provider implementation either, so a filesystem logger would throw
      // MissingPluginException here: completing at all proves the web path never touches it.
      final GleanLogger logger = await createGleanLogger(logsToFile: false);

      await logger.error('catalogue sync failed');
      expect(logger.file.readAll(), contains('catalogue sync failed'));
    },
  );

  test('the in-memory log keeps whole lines within its cap', () {
    final RotatingLogFile log = RotatingLogFile.memory(maxBytes: 60);
    for (var i = 0; i < 20; i++) {
      log.append('line $i');
    }

    final String kept = log.readAll();
    expect(kept, contains('line 19'));
    expect(kept, isNot(contains('line 0\n')));
    expect(kept.length, lessThanOrEqualTo(60));
    expect(kept, startsWith('line '));
  });
}
