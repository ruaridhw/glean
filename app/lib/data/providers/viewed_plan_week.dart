import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../util/week.dart';
import 'clock_provider.dart';

/// Shared UI selection, not a recipe-id navigation parameter. Manual addition
/// follows the last viewed week without replaying a mutation on tab focus.
final viewedPlanWeekProvider = NotifierProvider<ViewedPlanWeek, DateTime>(
  ViewedPlanWeek.new,
);

class ViewedPlanWeek extends Notifier<DateTime> {
  @override
  DateTime build() => startOfWeek(ref.read(clockProvider)());
  void select(DateTime date) => state = startOfWeek(date);
}
