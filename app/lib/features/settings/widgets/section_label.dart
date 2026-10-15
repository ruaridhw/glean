import 'package:flutter/material.dart';

/// A small uppercase section heading (RN's "sectionLabel" style).
///
/// Flutter's [TextStyle] has no `text-transform: uppercase` equivalent
/// (FINDINGS.md F-04) — the design system's `labelSmall` already carries the
/// right size/weight/letter-spacing, so this widget only adds the
/// `.toUpperCase()` call, once, rather than every call site remembering to.
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
