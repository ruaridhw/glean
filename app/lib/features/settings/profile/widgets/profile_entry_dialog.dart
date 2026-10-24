import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/design_system/design_system.dart';

import '../profile_presentation.dart';

/// Asks for one line of text to add to a profile list, or to replace a chip's text. Pops the trimmed text, or
/// `null` when cancelled or left blank.
class ProfileEntryDialog extends StatefulWidget {
  const ProfileEntryDialog({
    super.key,
    required this.title,
    required this.saveLabel,
    this.initial = '',
  });

  final String title;
  final String saveLabel;
  final String initial;

  @override
  State<ProfileEntryDialog> createState() => _ProfileEntryDialogState();
}

class _ProfileEntryDialogState extends State<ProfileEntryDialog> {
  late final TextEditingController _controller = TextEditingController(
    text: widget.initial,
  );

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _save() {
    final String text = _controller.text.trim();
    Navigator.of(context).pop(text.isEmpty ? null : text);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: TextField(
        key: const Key('profile.entry'),
        controller: _controller,
        autofocus: true,
        textCapitalization: TextCapitalization.sentences,
        textInputAction: TextInputAction.done,
        onSubmitted: (_) => _save(),
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        TextButton(
          key: const Key('profile.entry.save'),
          onPressed: _save,
          child: Text(widget.saveLabel),
        ),
      ],
    );
  }
}

/// Asks for one of the [mainProteins] and how many times a week it should appear: at least, at most, or both,
/// from 1 to 7. Pops the target, or `null` when cancelled. The keyboard's Done key saves, as the button does.
class ProteinTargetDialog extends StatefulWidget {
  const ProteinTargetDialog({
    super.key,
    required this.title,
    required this.saveLabel,
    this.initial,
  });

  final String title;
  final String saveLabel;
  final ProteinTarget? initial;

  @override
  State<ProteinTargetDialog> createState() => _ProteinTargetDialogState();
}

class _ProteinTargetDialogState extends State<ProteinTargetDialog> {
  late String? _protein = widget.initial?.protein;
  late final TextEditingController _min = TextEditingController(
    text: widget.initial?.minPerWeek?.toString() ?? '',
  );
  late final TextEditingController _max = TextEditingController(
    text: widget.initial?.maxPerWeek?.toString() ?? '',
  );
  String? _error;

  @override
  void dispose() {
    _min.dispose();
    _max.dispose();
    super.dispose();
  }

  void _save() {
    final String? protein = _protein;
    final int? min = int.tryParse(_min.text.trim());
    final int? max = int.tryParse(_max.text.trim());
    final String? error = protein == null
        ? 'Pick a protein'
        : proteinTargetError(min, max);
    if (error != null) {
      setState(() => _error = error);
      return;
    }
    Navigator.of(
      context,
    ).pop(ProteinTarget(protein: protein!, minPerWeek: min, maxPerWeek: max));
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return AlertDialog(
      title: Text(widget.title),
      scrollable: true,
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Wrap(
            spacing: tokens.spacing.sm,
            runSpacing: tokens.spacing.sm,
            children: <Widget>[
              for (final String protein in mainProteins)
                ChoiceChip(
                  key: Key('profile.protein.$protein'),
                  label: Text(proteinName(protein)),
                  selected: _protein == protein,
                  onSelected: (_) => setState(() => _protein = protein),
                ),
            ],
          ),
          SizedBox(height: tokens.spacing.md),
          GleanField(
            label: 'At least, per week',
            child: _CountField(
              fieldKey: const Key('profile.protein.min'),
              controller: _min,
              onDone: _save,
            ),
          ),
          SizedBox(height: tokens.spacing.md),
          GleanField(
            label: 'At most, per week',
            child: _CountField(
              fieldKey: const Key('profile.protein.max'),
              controller: _max,
              onDone: _save,
            ),
          ),
          if (_error case final String error) ...<Widget>[
            SizedBox(height: tokens.spacing.md),
            Text(
              error,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.error,
              ),
            ),
          ],
        ],
      ),
      actions: <Widget>[
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Cancel'),
        ),
        TextButton(
          key: const Key('profile.entry.save'),
          onPressed: _save,
          child: Text(widget.saveLabel),
        ),
      ],
    );
  }
}

class _CountField extends StatelessWidget {
  const _CountField({
    required this.fieldKey,
    required this.controller,
    required this.onDone,
  });

  final Key fieldKey;
  final TextEditingController controller;
  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    return TextField(
      key: fieldKey,
      controller: controller,
      keyboardType: TextInputType.number,
      textInputAction: TextInputAction.done,
      onSubmitted: (_) => onDone(),
      inputFormatters: <TextInputFormatter>[
        FilteringTextInputFormatter.digitsOnly,
        LengthLimitingTextInputFormatter(1),
      ],
      decoration: const InputDecoration(hintText: 'Optional'),
    );
  }
}
