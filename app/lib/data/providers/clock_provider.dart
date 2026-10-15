import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Time is a system boundary: production uses the wall clock; warm-week
/// transition tests can advance it without replacing plan repositories.
final clockProvider = Provider<DateTime Function()>((ref) => DateTime.now);
