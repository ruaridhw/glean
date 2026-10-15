import 'dart:io';

/// An append-only text log capped near [maxBytes]: when the next line would overflow it, the current file
/// becomes `<name>.1` (replacing the previous one) and a fresh file starts, so the newest lines are always kept.
class RotatingLogFile {
  RotatingLogFile(this.file, {this.maxBytes = 256 * 1024});

  final File file;
  final int maxBytes;

  File get _previous => File('${file.path}.1');

  void append(String line) {
    file.parent.createSync(recursive: true);
    if (file.existsSync() && file.lengthSync() + line.length + 1 > maxBytes) {
      file.renameSync(_previous.path);
    }
    file.writeAsStringSync('$line\n', mode: FileMode.append, flush: true);
  }

  /// The retained log, oldest line first.
  String readAll() {
    return <File>[
      _previous,
      file,
    ].where((f) => f.existsSync()).map((f) => f.readAsStringSync()).join();
  }
}
