/// The V1 Generate error catalogue (spec §6.3, copy approved 2026-10-22). One place decides what the user reads
/// and what the error offers: the controller turns every way a run can end into a [GenerateFailure], and the
/// Plan tab renders it. Internal codes never reach the user, recognised or not.
library;

import 'package:glean/api/api_exception.dart';

/// What went wrong, in the terms the catalogue speaks. The last value catches everything the app does not
/// recognise, including a lost connection and an unexpected local failure.
enum GenerateFailureKind {
  noEligibleRecipes,
  rateLimited,
  modelError,
  stalled,
  workerFailed,
  invalidRequest,
  unknown,
}

/// What the error offers beside its message; `null` means it offers nothing.
enum GenerateFailureAction { openSettings, retry, report }

/// A Generate attempt that ended with something to tell the user. Thrown by the controller, so the screen can
/// render the catalogue without reinterpreting transport exceptions.
class GenerateFailure implements Exception {
  const GenerateFailure(this.kind, {this.retryAfterMinutes});

  /// The `rate_limited` message names a wait. A session's error carries the figure; a create-time 429 usually
  /// does not, and the limit's own window is an hour, so that is the honest stand-in.
  static const int defaultRetryAfterMinutes = 60;

  factory GenerateFailure.fromCode(String? code, {int? retryAfterMinutes}) {
    return switch (code) {
      'no_eligible_recipes' => const GenerateFailure(
        GenerateFailureKind.noEligibleRecipes,
      ),
      'rate_limited' => GenerateFailure(
        GenerateFailureKind.rateLimited,
        retryAfterMinutes: retryAfterMinutes,
      ),
      'model_error' => const GenerateFailure(GenerateFailureKind.modelError),
      'worker_failed' => const GenerateFailure(
        GenerateFailureKind.workerFailed,
      ),
      'invalid_request' => const GenerateFailure(
        GenerateFailureKind.invalidRequest,
      ),
      // An unknown code is still the generic message: the code stays internal.
      _ => const GenerateFailure(GenerateFailureKind.unknown),
    };
  }

  /// A failure before the session exists: a 429 has its own copy, and everything else (signed out, no network,
  /// a rejected request) gets the generic message and a retry.
  factory GenerateFailure.fromApi(ApiException error) {
    if (error is ApiRateLimitException) {
      return GenerateFailure(
        GenerateFailureKind.rateLimited,
        retryAfterMinutes: error.retryAfterMinutes,
      );
    }
    return const GenerateFailure(GenerateFailureKind.unknown);
  }

  /// Maps whatever the controller is holding back to the catalogue. A [GenerateFailure] passes through; any
  /// other throwable (a database failure while committing) is a failure to report generically.
  factory GenerateFailure.from(Object error) {
    if (error is GenerateFailure) return error;
    if (error is ApiException) return GenerateFailure.fromApi(error);
    return const GenerateFailure(GenerateFailureKind.unknown);
  }

  final GenerateFailureKind kind;

  /// How long the backend asked the user to wait, when it said so.
  final int? retryAfterMinutes;

  /// The approved copy, verbatim.
  String get message => switch (kind) {
    GenerateFailureKind.noEligibleRecipes =>
      'No recipes fit your diet and time limit.',
    GenerateFailureKind.rateLimited =>
      "You've used too many AI credits. "
          'Try again in ${retryAfterMinutes ?? defaultRetryAfterMinutes} minutes.',
    GenerateFailureKind.modelError ||
    GenerateFailureKind.workerFailed ||
    GenerateFailureKind.unknown => 'Something went wrong planning your week.',
    GenerateFailureKind.stalled => 'Planning stopped responding.',
    GenerateFailureKind.invalidRequest => "Glean couldn't read this request.",
  };

  GenerateFailureAction? get action => switch (kind) {
    GenerateFailureKind.noEligibleRecipes => GenerateFailureAction.openSettings,
    GenerateFailureKind.rateLimited => null,
    GenerateFailureKind.modelError ||
    GenerateFailureKind.stalled ||
    GenerateFailureKind.workerFailed ||
    GenerateFailureKind.unknown => GenerateFailureAction.retry,
    GenerateFailureKind.invalidRequest => GenerateFailureAction.report,
  };

  /// The action's label, so the screen never invents one.
  String? get actionLabel => switch (action) {
    GenerateFailureAction.openSettings => 'Open Settings',
    GenerateFailureAction.retry => 'Retry',
    GenerateFailureAction.report => 'Report',
    null => null,
  };

  @override
  String toString() => 'GenerateFailure(${kind.name})';
}
