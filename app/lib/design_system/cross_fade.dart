import 'package:flutter/material.dart';

/// Cross-fades between a skeleton and its loaded content via
/// [AnimatedSwitcher] (AC-TRN-01) — never a hard cut, and never a bare
/// spinner. `FLUTTER_MIGRATION.md` §7 specifically calls out recipe detail's
/// bare spinner as the odd one out (every other screen already uses a
/// skeleton); the fix is to standardise on this everywhere loading
/// transitions to content, not to add a spinner elsewhere.
///
/// Usage: pass whichever of [skeleton]/[content] is current as [child]; a
/// [ValueKey] distinguishes them so [AnimatedSwitcher] treats a
/// skeleton→content swap as a transition rather than an in-place rebuild.
class GleanCrossFade extends StatelessWidget {
  const GleanCrossFade({
    super.key,
    required this.showSkeleton,
    required this.skeleton,
    required this.content,
    this.duration = const Duration(milliseconds: 220),
  });

  final bool showSkeleton;
  final Widget skeleton;
  final Widget content;
  final Duration duration;

  @override
  Widget build(BuildContext context) {
    return AnimatedSwitcher(
      duration: duration,
      child: showSkeleton
          ? KeyedSubtree(
              key: const ValueKey<String>('skeleton'),
              child: skeleton,
            )
          : KeyedSubtree(
              key: const ValueKey<String>('content'),
              child: content,
            ),
    );
  }
}
