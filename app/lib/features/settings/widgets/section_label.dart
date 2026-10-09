import 'package:flutter/material.dart';

/// A small uppercase section heading. [TextStyle] has no `text-transform: uppercase`; `labelSmall` already
/// carries the right size/weight/letter-spacing, so this widget only adds `.toUpperCase()` once rather than
/// every call site.
class SectionLabel extends StatelessWidget {
  const SectionLabel(this.text, {super.key});

  final String text;

  @override
  Widget build(BuildContext context) {
    return Text(
      text.toUpperCase(),
      style: Theme.of(context).textTheme.labelSmall,
    );
  }
}
