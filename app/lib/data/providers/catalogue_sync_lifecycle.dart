import 'dart:async';

import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/providers/api_providers.dart';
import '../../auth/auth.dart';
import '../catalogue_sync.dart';
import 'clock_provider.dart';
import 'repository_providers.dart';

final Provider<CatalogueSync> catalogueSyncProvider = Provider<CatalogueSync>(
  (ref) => CatalogueSync(
    api: ref.watch(apiClientProvider),
    repository: ref.watch(catalogueRepositoryProvider),
    now: ref.watch(clockProvider),
  ),
);

/// Keeps the local catalogue current without the user waiting on it: starts a sync in the background when the app
/// launches, when it returns to the foreground and when the user signs in. [child] is always built immediately.
class CatalogueSyncLifecycle extends ConsumerStatefulWidget {
  const CatalogueSyncLifecycle({required this.child, super.key});

  final Widget child;

  @override
  ConsumerState<CatalogueSyncLifecycle> createState() =>
      _CatalogueSyncLifecycleState();
}

class _CatalogueSyncLifecycleState extends ConsumerState<CatalogueSyncLifecycle>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _sync());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) _sync();
  }

  void _sync() {
    if (!mounted) return;
    if (ref.read(authControllerProvider).status == AuthStatus.signedOut) {
      return;
    }
    unawaited(
      ref.read(catalogueSyncProvider).sync().catchError((
        Object error,
        StackTrace stack,
      ) {
        // Network and server failures are handled inside the sync; this is a local failure (the database).
        FlutterError.reportError(
          FlutterErrorDetails(
            exception: error,
            stack: stack,
            library: 'catalogue sync',
          ),
        );
      }),
    );
  }

  @override
  Widget build(BuildContext context) {
    ref.listen(authControllerProvider.select((s) => s.status), (
      AuthStatus? previous,
      AuthStatus next,
    ) {
      if (previous == AuthStatus.signedOut && next != AuthStatus.signedOut) {
        _sync();
      }
    });
    return widget.child;
  }
}
