import 'dart:async';

import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// A free-text profile answer that saves itself: [onSave] runs once typing pauses, when the field loses focus,
/// and on the way out if an edit is still waiting. A new [value] from storage replaces the text only while the
/// field is not being edited, so the stream echoing a save never fights the cursor.
class ProfileTextField extends StatefulWidget {
  const ProfileTextField({
    super.key,
    required this.label,
    required this.hint,
    required this.value,
    required this.onSave,
  });

  final String label;
  final String hint;
  final String value;
  final void Function(String text) onSave;

  @override
  State<ProfileTextField> createState() => _ProfileTextFieldState();
}

class _ProfileTextFieldState extends State<ProfileTextField> {
  static const Duration _debounce = Duration(milliseconds: 500);

  late final TextEditingController _controller = TextEditingController(
    text: widget.value,
  );
  final FocusNode _focus = FocusNode();
  Timer? _pending;

  @override
  void initState() {
    super.initState();
    _focus.addListener(() {
      if (!_focus.hasFocus) _flush();
    });
  }

  @override
  void didUpdateWidget(ProfileTextField oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (!_focus.hasFocus &&
        _pending == null &&
        _controller.text != widget.value) {
      _controller.text = widget.value;
    }
  }

  void _flush() {
    if (_pending == null) return;
    _pending!.cancel();
    _pending = null;
    widget.onSave(_controller.text.trim());
  }

  @override
  void dispose() {
    _flush();
    _focus.dispose();
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return GleanField(
      label: widget.label,
      child: TextField(
        controller: _controller,
        focusNode: _focus,
        minLines: 1,
        maxLines: 4,
        textCapitalization: TextCapitalization.sentences,
        decoration: InputDecoration(hintText: widget.hint),
        onTapOutside: (_) => _focus.unfocus(),
        onChanged: (_) {
          _pending?.cancel();
          _pending = Timer(_debounce, _flush);
        },
      ),
    );
  }
}
