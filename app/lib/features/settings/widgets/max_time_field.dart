import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:glean/design_system/design_system.dart';

import '../settings_presentation.dart';

/// The "max active cooking time" field. A "minutes" unit is always visible (`suffixText`), and the 1–480 bound
/// is shown before it's violated: [helperText] states it unconditionally, replaced by [errorText] once the
/// input is out of range. [FilteringTextInputFormatter.digitsOnly] means the field can never hold a non-digit.
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
