// The Developer card's restore action needs the app's own database file, which only the native builds have. On
// the web dev loop the action stays visible but disabled, with the reason, so the screen explains itself
// instead of offering an action that cannot work there.
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/settings/widgets/developer_section.dart';

const Key _restoreButton = Key('settings.restoreBackup');
const Key _restoreUnavailable = Key('settings.restoreUnavailable');

Widget _section({bool restoreUnavailable = false}) {
  return MaterialApp(
    theme: gleanLightTheme,
    home: Scaffold(
      body: DeveloperSection(
        exporting: false,
        onExportDiagnostics: () {},
        restoring: false,
        onRestoreBackup: () {},
        restoreUnavailable: restoreUnavailable,
      ),
    ),
  );
}

TextButton _button(WidgetTester tester) =>
    tester.widget<TextButton>(find.byKey(_restoreButton));

void main() {
  testWidgets('restore is offered where the app has a database file', (
    WidgetTester tester,
  ) async {
    await tester.pumpWidget(_section());

    expect(_button(tester).onPressed, isNotNull);
    expect(find.byKey(_restoreUnavailable), findsNothing);
  });

  testWidgets(
    'restore is disabled there with the reason shown where it cannot work',
    (WidgetTester tester) async {
      await tester.pumpWidget(_section(restoreUnavailable: true));

      expect(_button(tester).onPressed, isNull);
      expect(find.byKey(_restoreUnavailable), findsOneWidget);
      expect(
        find.textContaining('not available in the web build'),
        findsOneWidget,
      );
    },
  );
}
