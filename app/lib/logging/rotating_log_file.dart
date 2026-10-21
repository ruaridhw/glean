import 'dart:io';

/// An append-only text log capped near [maxBytes]: when the next line would overflow it, the current file
/// becomes `<name>.1` (replacing the previous one) and a fresh file starts, so the newest lines are always kept.
///
/// [RotatingLogFile.memory] is the same contract without a filesystem, for platforms that have none (the web
/// build): lines are held in memory and the oldest are dropped at the same cap.
class RotatingLogFile {
  RotatingLogFile(File this._file, {this.maxBytes = 256 * 1024})
    : _memory = null;

  RotatingLogFile.memory({this.maxBytes = 256 * 1024})
    : _file = null,
      _memory = StringBuffer();

  final File? _file;
  final StringBuffer? _memory;
  final int maxBytes;

  File get _previous => File('${_file!.path}.1');

  void append(String line) {
    final File? file = _file;
    if (file == null) {
      _memory!.write('$line\n');
      _trimToCap();
      return;
    }
    file.parent.createSync(recursive: true);
    if (file.existsSync() && file.lengthSync() + line.length + 1 > maxBytes) {
      file.renameSync(_previous.path);
    }
    file.writeAsStringSync('$line\n', mode: FileMode.append, flush: true);
  }

  /// The retained log, oldest line first.
  String readAll() {
    final File? file = _file;
    if (file == null) return _memory!.toString();
    return <File>[
      _previous,
      file,
    ].where((f) => f.existsSync()).map((f) => f.readAsStringSync()).join();
  }

  /// Drops the oldest whole lines until what is left fits [maxBytes].
  void _trimToCap() {
    final StringBuffer memory = _memory!;
    if (memory.length <= maxBytes) return;
    final String text = memory.toString();
    final int firstKept = text.indexOf('\n', text.length - maxBytes);
    memory
      ..clear()
      ..write(firstKept == -1 ? text : text.substring(firstKept + 1));
  }
}
