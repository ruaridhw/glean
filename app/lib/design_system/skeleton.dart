import 'package:flutter/material.dart';

import 'tokens.dart';

/// A shimmering placeholder block. [TweenAnimationBuilder] drives the pulse with no `AnimationController`:
/// each `onEnd` flips the target and `setState` starts the next leg.
class SkeletonBox extends StatefulWidget {
  const SkeletonBox({
    super.key,
    required this.width,
    required this.height,
    this.borderRadius,
  });

  final double width;
  final double height;
  final BorderRadius? borderRadius;

  @override
  State<SkeletonBox> createState() => _SkeletonBoxState();
}

class _SkeletonBoxState extends State<SkeletonBox> {
  static const Duration _legDuration = Duration(milliseconds: 1000);
  static const double _dim = 0.3;
  static const double _bright = 1.0;

  // Which leg of the pulse we're animating *towards*. Flipped in `onEnd` so
  // the next build requests the opposite target — this is the whole loop.
  bool _towardsBright = true;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return TweenAnimationBuilder<double>(
      // `begin` only matters for the very first frame (afterwards
      // TweenAnimationBuilder animates from whatever the current value is);
      // it's supplied unconditionally so that first frame actually has
      // begin != end and therefore animates instead of snapping.
      tween: Tween<double>(begin: _dim, end: _towardsBright ? _bright : _dim),
      duration: _legDuration,
      curve: Curves.easeInOut,
      onEnd: () => setState(() => _towardsBright = !_towardsBright),
      builder: (BuildContext context, double opacity, Widget? child) {
        return Opacity(opacity: opacity, child: child);
      },
      child: Container(
        width: widget.width,
        height: widget.height,
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius:
              widget.borderRadius ?? BorderRadius.circular(tokens.radius.sm),
        ),
      ),
    );
  }
}
