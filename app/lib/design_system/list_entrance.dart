import 'package:flutter/material.dart';

/// A subtle "settle into place" entrance for a newly-inserted list row
/// (FLUTTER_MIGRATION.md §7, AC-TRN-02).
///
/// Removal already animates for free via `Dismissible` (see
/// `swipe_to_delete.dart`), but insertion had no animation anywhere in
/// Pantry, Shop or Meals — new rows just popped into existence. Those three
/// screens render their lists from a declarative drift stream (a fresh
/// `ListView`/`Column` built from whatever the stream just emitted), not
/// from imperative insert/remove calls, so `AnimatedList`'s
/// insert/removeItem API doesn't fit the data flow; this is the
/// implicit-animation alternative FLUTTER_MIGRATION.md §7 allows instead.
///
/// **Must be given a [key] matching the row's own stable identity (its
/// database id) and must be the direct list child** — not nested inside an
/// unkeyed wrapper. That's what lets Flutter's element reconciliation tell
/// "this row already existed and merely shifted position" (state preserved,
/// no replay) apart from "this key never existed before" (fresh state, so
/// it animates in) when an insertion shifts everything after it. A
/// `SliverChildListDelegate` (i.e. `ListView(children: [...])`, not
/// `ListView.builder`) is required for the same reason — the builder
/// delegate only reorders by key with an explicit `findChildIndexCallback`,
/// which none of these lists supply.
class GleanListEntrance extends StatefulWidget {
  const GleanListEntrance({required super.key, required this.child});

  final Widget child;

  @override
  State<GleanListEntrance> createState() => _GleanListEntranceState();
}

class _GleanListEntranceState extends State<GleanListEntrance> {
  bool _settled = false;

  @override
  void initState() {
    super.initState();
    // Starts off-place/transparent and settles on the *next* frame rather
    // than at construction — animating away from the very first frame a new
    // key appears is what reads as "inserted", not "always was here".
    WidgetsBinding.instance.addPostFrameCallback((Duration _) {
      if (mounted) setState(() => _settled = true);
    });
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedSlide(
      offset: _settled ? Offset.zero : const Offset(0, 0.08),
      duration: const Duration(milliseconds: 220),
      curve: Curves.easeOut,
      child: AnimatedOpacity(
        opacity: _settled ? 1 : 0,
        duration: const Duration(milliseconds: 220),
        curve: Curves.easeOut,
        child: widget.child,
      ),
    );
  }
}
