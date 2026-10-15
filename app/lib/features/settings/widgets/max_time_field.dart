import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:glean/design_system/design_system.dart';

import '../settings_presentation.dart';

/// The "max active cooking time" field.
///
/// Two RN gaps this closes (AC-UX-05):
/// - a **"minutes" unit** is always visible (`suffixText`), not implied;
/// - the **1–480 bound is shown before it's violated** — [helperText] states
///   it unconditionally, replaced by [errorText] only once the current input
///   is actually out of range, rather than the bound appearing for the first
///   time as an error message.
///
/// [FilteringTextInputFormatter.digitsOnly] rules out the RN bug where
/// non-numeric input could round-trip into a persisted `NaN` (§11) — there
/// is no non-digit character this field can ever contain.
class MaxTimeField extends StatelessWidget {
  const MaxTimeField({
    super.key,
    required this.controller,
    required this.errorText,
    required this.onChanged,
  });

  final TextEditingController controller;
  final String? errorText;
  final ValueChanged<String> onChanged;

  static String get boundHint =>
      'Leave blank for no limit, or enter ${SettingsOptionRanges.maxActiveTimeMins.min}'
      '–${SettingsOptionRanges.maxActiveTimeMins.max} minutes.';

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Max active cooking time',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            SizedBox(height: tokens.spacing.sm),
            TextField(
              controller: controller,
              keyboardType: TextInputType.number,
              inputFormatters: <TextInputFormatter>[
                FilteringTextInputFormatter.digitsOnly,
              ],
              onChanged: onChanged,
              decoration: InputDecoration(
                suffixText: 'min',
                helperText: boundHint,
                helperMaxLines: 2,
                errorText: errorText,
                errorMaxLines: 2,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
