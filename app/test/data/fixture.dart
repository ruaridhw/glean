// Shared in-memory drift fixture for data-layer tests.
//
// `NativeDatabase.memory()` runs the same `onCreate` migration as
// production (schema creation + seeding), verified working headless on
// this box — so these tests exercise the real seed data and real
// SQL/foreign-key behaviour, not a parallel test-only fixture.
import 'package:drift/native.dart';
import 'package:glean/data/database.dart';

GleanDatabase createTestDatabase() {
  return GleanDatabase(NativeDatabase.memory());
}
