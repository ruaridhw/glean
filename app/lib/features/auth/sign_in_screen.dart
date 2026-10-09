/// Google-via-Cognito sign-in (FLUTTER_MIGRATION.md §5/§6 — Google-only sign-in
/// is unchanged). "Sign in with Google" is called out in §7 as "the single
/// most important tap in the app"; it and a successful sign-in both fire a
/// haptic through the design-system ladder (AC-HAP-05), mirroring how
/// `SettingsScreen._handleSignOut` fires sign-out's haptic — never inside
/// `AuthController` itself, to avoid the double-buzz bug (AC-HAP-03).
library;

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/auth/auth.dart';
import 'package:glean/design_system/design_system.dart';

class SignInScreen extends ConsumerStatefulWidget {
  const SignInScreen({super.key});

  @override
  ConsumerState<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends ConsumerState<SignInScreen> {
  bool _isSigningIn = false;

  Future<void> _handleSignIn() async {
    if (_isSigningIn) return;
    // The default tappable acknowledgement, fired immediately — not gated
    // on the (slow, network-bound) result below.
    ref.read(hapticsProvider).lightImpact();
    setState(() => _isSigningIn = true);
    try {
      await ref.read(authControllerProvider.notifier).signIn();
      if (!mounted) return;
      // A real data commit: the device now holds a persisted session.
      // go_router's redirect listener sends the user off this screen on its
      // own once `authStatusProvider` flips to `active` — no navigation here.
      ref.read(hapticsProvider).mediumImpact();
    } on AuthException catch (error) {
      if (error.cancelled) return; // the user closed the browser themselves
      if (!mounted) return;
      GleanSnackBar.show(context, error.message);
    } catch (_) {
      if (!mounted) return;
      GleanSnackBar.show(context, 'Sign in failed. Please try again.');
    } finally {
      if (mounted) setState(() => _isSigningIn = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final TextTheme textTheme = Theme.of(context).textTheme;
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: EdgeInsets.all(tokens.spacing.xl),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: <Widget>[
              const _BrandIconTile(),
              SizedBox(height: tokens.spacing.xl),
              Text('Sign in', style: textTheme.titleMedium),
              SizedBox(height: tokens.spacing.xs),
              Text('Waste less.\nCook better.', style: textTheme.headlineLarge),
              SizedBox(height: tokens.spacing.xxl),
              SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: _isSigningIn
                      ? null
                      : () => unawaited(_handleSignIn()),
                  style: FilledButton.styleFrom(
                    backgroundColor: tokens.ink,
                    foregroundColor: Colors.white,
                    disabledBackgroundColor: tokens.ink.withValues(alpha: 0.5),
                  ),
                  child: _isSigningIn
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: Colors.white,
                          ),
                        )
                      : const Text('Sign in with Google'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Extracted so it has its own `const` rebuild scope (AC-DS-14) — this
/// screen's only sub-widget.
class _BrandIconTile extends StatelessWidget {
  const _BrandIconTile();

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Container(
      width: 72,
      height: 72,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: tokens.primaryLight,
        borderRadius: BorderRadius.circular(tokens.radius.xl),
      ),
      child: const GleanMark(size: 40),
    );
  }
}
