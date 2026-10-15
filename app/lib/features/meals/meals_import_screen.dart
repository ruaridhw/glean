/// Import a recipe from a URL (`POST /recipes/import-url`). Dedupes against
/// the saved library like search does, and says "already saved" instead of
/// inserting a duplicate row.
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/recipes.dart';
import 'package:glean/api/providers/api_providers.dart';
import 'package:glean/api/text_input.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/router/app_routes.dart';
import 'package:go_router/go_router.dart';

import 'actions.dart';

class MealsImportScreen extends ConsumerStatefulWidget {
  const MealsImportScreen({super.key});

  @override
  ConsumerState<MealsImportScreen> createState() => _MealsImportScreenState();
}

class _MealsImportScreenState extends ConsumerState<MealsImportScreen> {
  late final TextEditingController _urlController;
  bool _importing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _urlController = TextEditingController();
    _urlController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _urlController.dispose();
    super.dispose();
  }

  bool get _canImport => toRequiredSubmittedText(_urlController.text) != null;

  Future<void> _import() async {
    final String? url = toRequiredSubmittedText(_urlController.text);
    if (url == null) return;

    setState(() {
      _importing = true;
      _error = null;
    });

    final RecipeOut detail;
    try {
      detail = await ref
          .read(apiClientProvider)
          .importRecipeFromUrl(ImportUrlRequest(url: url));
    } catch (error) {
      if (!mounted) return;
      setState(() {
        _importing = false;
        _error = error is ApiRateLimitException
            ? error.userMessage
            : 'Could not import this recipe. Check the link and try again.';
      });
      return;
    }
    if (!mounted) return;

    final existing = await ref
        .read(recipesRepositoryProvider)
        .getByExternalId(
          externalId: detail.externalId,
          userId: ref.read(currentUserIdProvider),
        );
    if (!mounted) return;

    if (existing != null) {
      setState(() => _importing = false);
      GleanSnackBar.show(context, 'Already saved');
      unawaited(
        context.pushNamed(
          AppRoutes.mealsDetail.name,
          pathParameters: <String, String>{'id': '${existing.id}'},
        ),
      );
      return;
    }

    final int id = await saveApiRecipe(ref, detail);
    if (!mounted) return;
    ref.read(hapticsProvider).mediumImpact();
    setState(() => _importing = false);
    unawaited(
      context.pushNamed(
        AppRoutes.mealsDetail.name,
        pathParameters: <String, String>{'id': '$id'},
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Scaffold(
      appBar: AppBar(title: const Text('Import from URL')),
      body: Padding(
        padding: EdgeInsets.all(tokens.spacing.lg),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              mainAxisSize: MainAxisSize.min,
              children: <Widget>[
                Icon(
                  Icons.link_rounded,
                  size: 28,
                  color: Theme.of(context).colorScheme.primary,
                ),
                SizedBox(height: tokens.spacing.sm),
                Text(
                  'Recipe link',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                SizedBox(height: tokens.spacing.xs),
                Text(
                  'Paste a recipe URL and Glean will extract the details.',
                  style: Theme.of(context).textTheme.bodyMedium,
                ),
                SizedBox(height: tokens.spacing.lg),
                TextField(
                  controller: _urlController,
                  autocorrect: false,
                  keyboardType: TextInputType.url,
                  textInputAction: TextInputAction.go,
                  onSubmitted: (_) => _import(),
                  decoration: const InputDecoration(hintText: 'https://…'),
                ),
                if (_error != null) ...<Widget>[
                  SizedBox(height: tokens.spacing.sm),
                  Text(
                    _error!,
                    style: Theme.of(
                      context,
                    ).textTheme.bodySmall?.copyWith(color: tokens.warning),
                  ),
                ],
                SizedBox(height: tokens.spacing.lg),
                FilledButton(
                  onPressed: (_importing || !_canImport) ? null : _import,
                  child: _importing
                      ? SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Theme.of(context).colorScheme.onPrimary,
                          ),
                        )
                      : const Text('Import'),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
