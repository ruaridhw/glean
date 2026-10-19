import 'package:flutter/material.dart';

import 'tokens.dart';

/// A persistent label outside a filled input's background and focus border.
///
/// The child owns its decoration and validation, but must not set labelText.
class GleanField extends StatelessWidget {
  const GleanField({super.key, required this.label, required this.child});

  final String label;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final padding =
        theme.inputDecorationTheme.contentPadding ?? EdgeInsets.zero;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Padding(
          padding: EdgeInsetsDirectional.only(
            start: padding.resolve(Directionality.of(context)).left,
            bottom: context.tokens.spacing.sm,
          ),
          child: ExcludeSemantics(
            child: Text(label, style: theme.textTheme.labelLarge),
          ),
        ),
        Semantics(label: label, child: child),
      ],
    );
  }
}
