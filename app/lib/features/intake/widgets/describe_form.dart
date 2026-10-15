import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

/// Shared UI for "describe what you [bought/need]", the free-text sibling of receipt scan, used by both describe
/// screens. It owns the text field's lifecycle; which endpoint parses the text and where it navigates stays in
/// each caller.
class DescribeForm extends StatefulWidget {
  const DescribeForm({
    super.key,
    required this.hintText,
    required this.placeholder,
    required this.buttonLabel,
    required this.isLoading,
    required this.errorMessage,
    required this.onSubmit,
  });

  /// The explanatory line above the text field.
  final String hintText;

  /// The text field's own placeholder.
  final String placeholder;

  final String buttonLabel;

  /// Drives the submit button's spinner and disables re-submission while
  /// true — reflects the caller's watched `AsyncValue.isLoading`, not local
  /// state, so it can never drift from the real request.
  final bool isLoading;

  /// Null when there is nothing to show. Plain text rather than a typed error: callers have already turned it
  /// into the right message for their failure mode.
  final String? errorMessage;

  /// Called with the trimmed text once the user taps submit. Never called
  /// with blank text or while [isLoading] — the button is disabled for both.
  final ValueChanged<String> onSubmit;

  @override
  State<DescribeForm> createState() => _DescribeFormState();
}

class _DescribeFormState extends State<DescribeForm> {
  final TextEditingController _controller = TextEditingController();

  @override
  void initState() {
    super.initState();
    _controller.addListener(_onTextChanged);
  }

  void _onTextChanged() => setState(() {});

  @override
  void dispose() {
    _controller.removeListener(_onTextChanged);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final bool canSubmit =
        _controller.text.trim().isNotEmpty && !widget.isLoading;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Text(widget.hintText, style: Theme.of(context).textTheme.bodyMedium),
        SizedBox(height: tokens.spacing.md),
        Expanded(
          child: TextField(
            controller: _controller,
            autofocus: true,
            expands: true,
            maxLines: null,
            textAlignVertical: TextAlignVertical.top,
            decoration: InputDecoration(hintText: widget.placeholder),
          ),
        ),
        if (widget.errorMessage != null) ...<Widget>[
          SizedBox(height: tokens.spacing.md),
          Text(
            widget.errorMessage!,
            style: TextStyle(color: Theme.of(context).colorScheme.error),
          ),
        ],
        SizedBox(height: tokens.spacing.lg),
        FilledButton(
          onPressed: canSubmit
              ? () => widget.onSubmit(_controller.text.trim())
              : null,
          child: widget.isLoading
              ? const SizedBox(
                  width: 20,
                  height: 20,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : Text(widget.buttonLabel),
        ),
      ],
    );
  }
}
