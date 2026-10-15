import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:glean/auth/auth.dart';
import 'package:glean/data/providers/catalogue_sync_lifecycle.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import '../support/harness.dart';

final String _emptyCatalogue = jsonEncode(<String, Object?>{
  'version': 0,
  'groups': jsonDecode(
    File('test/data/fixtures/catalogue_groups.json').readAsStringSync(),
  ),
  'items': <Object?>[],
  'aliases': <Object?>[],
});

void main() {
  late List<Uri> requests;
  late Completer<http.Response>? hold;
  late http.Response Function() reply;

  setUp(() {
    requests = <Uri>[];
    hold = null;
    reply = () => http.Response(_emptyCatalogue, 200);
  });

  MockClient client() => MockClient((request) async {
    requests.add(request.url);
    if (hold != null) return hold!.future;
    return reply();
  });

  Future<void> pumpApp(WidgetTester tester, AppTestHarness harness) =>
      tester.pumpWidget(
        UncontrolledProviderScope(
          container: harness.container,
          child: const Directionality(
            textDirection: TextDirection.ltr,
            child: CatalogueSyncLifecycle(child: Text('the app')),
          ),
        ),
      );

  gleanWidgetTest('the app is on screen at once and a sync starts on launch '
      'without waiting for the network', (tester) async {
    hold = Completer<http.Response>();
    final harness = AppTestHarness(httpClient: client());
    addTearDown(harness.dispose);

    await pumpApp(tester, harness);

    expect(find.text('the app'), findsOneWidget);
    await tester.runAsync(() => Future<void>.delayed(Duration.zero));
    expect(requests.single.path, '/catalogue');
    expect(requests.single.queryParameters['since'], '0');
    hold!.complete(http.Response(_emptyCatalogue, 200));
    await tester.runAsync(() => Future<void>.delayed(Duration.zero));
  });

  gleanWidgetTest('coming back to the app syncs again', (tester) async {
    final harness = AppTestHarness(httpClient: client());
    addTearDown(harness.dispose);
    await pumpApp(tester, harness);
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 50)),
    );
    expect(requests, hasLength(1));

    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 50)),
    );

    expect(requests, hasLength(2));
  });

  gleanWidgetTest('nothing is requested while signed out, and signing in '
      'starts the sync', (tester) async {
    final harness = AppTestHarness(
      httpClient: client(),
      authStatus: AuthStatus.signedOut,
    );
    addTearDown(harness.dispose);
    await pumpApp(tester, harness);
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 50)),
    );
    expect(requests, isEmpty);

    harness.container
        .read(authControllerProvider.notifier)
        .debugSetSnapshot(
          const AuthSessionSnapshot(status: AuthStatus.active, userId: 'u'),
        );
    await tester.pump();
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 50)),
    );

    expect(requests, hasLength(1));
  });

  gleanWidgetTest('an offline sync never disturbs the screen', (tester) async {
    reply = () => throw const SocketException('offline');
    final harness = AppTestHarness(httpClient: client());
    addTearDown(harness.dispose);

    await pumpApp(tester, harness);
    await tester.runAsync(
      () => Future<void>.delayed(const Duration(milliseconds: 50)),
    );

    expect(requests, hasLength(1));
    expect(find.text('the app'), findsOneWidget);
    expect(tester.takeException(), isNull);
  });
}
