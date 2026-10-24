import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/api/models/profile.dart';
import 'package:glean/design_system/design_system.dart';

import '../providers/interview_controller.dart';

/// The taste interview: a chat with the planner's interviewer in the middle slot of first run. The household
/// answers as many of up to seven turns as they like, may skip any of them or all of them, and confirms the
/// two-line summary at the end — which is the only moment the profile is saved.
///
/// The screen owns which page is showing; this owns the conversation, so tapping Back from the pantry and
/// returning finds the interview exactly as it was left.
class OnboardingTastePage extends ConsumerStatefulWidget {
  const OnboardingTastePage({
    required this.onConfirmed,
    required this.onBack,
    super.key,
  });

  /// The profile was confirmed and saved: first run carries on to the pantry.
  final VoidCallback onConfirmed;

  /// Back to the basics page. The transcript is kept, so returning costs no further calls.
  final VoidCallback onBack;

  @override
  ConsumerState<OnboardingTastePage> createState() =>
      _OnboardingTastePageState();
}

class _OnboardingTastePageState extends ConsumerState<OnboardingTastePage> {
  final TextEditingController _composer = TextEditingController();
  final Set<String> _chosen = <String>{};
  final ScrollController _chat = ScrollController();
  int _lastContentLength = -1;

  @override
  void initState() {
    super.initState();
    // The first question is a paid call, so it starts once the page is actually on screen rather than while
    // the tree is still building.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) {
        unawaited(ref.read(interviewControllerProvider.notifier).begin());
      }
    });
  }

  @override
  void dispose() {
    _composer.dispose();
    _chat.dispose();
    super.dispose();
  }

  void _answer() {
    final String text = _composer.text;
    final List<String> options = _chosen.toList();
    if (text.trim().isEmpty && options.isEmpty) return;
    ref.read(hapticsProvider).lightImpact();
    unawaited(
      ref
          .read(interviewControllerProvider.notifier)
          .answer(text: text, options: options),
    );
  }

  void _skip() {
    ref.read(hapticsProvider).lightImpact();
    unawaited(ref.read(interviewControllerProvider.notifier).skip());
  }

  /// The composer is cleared only once a turn has been accepted (the transcript grew), never when a send starts
  /// or fails: after a failure the household has to be able to read, and correct, what Retry will send.
  void _clearWhenAccepted(InterviewState? previous, InterviewState next) {
    if (next.transcript.length <= (previous?.transcript.length ?? 0)) return;
    _composer.clear();
    setState(_chosen.clear);
  }

  void _retry() {
    ref.read(hapticsProvider).lightImpact();
    unawaited(ref.read(interviewControllerProvider.notifier).retry());
  }

  Future<void> _confirm() async {
    final bool saved = await ref
        .read(interviewControllerProvider.notifier)
        .confirm();
    if (!mounted) return;
    ref.read(hapticsProvider).mediumImpact();
    if (!saved) {
      GleanSnackBar.show(
        context,
        'Could not save your profile — you can set it up later in Settings.',
      );
    }
    widget.onConfirmed();
  }

  /// Keeps the newest turn in view: the chat is the record, so the end of it is where the household is.
  void _keepChatInView(int contentLength) {
    if (contentLength == _lastContentLength) return;
    _lastContentLength = contentLength;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted || !_chat.hasClients) return;
      _chat.animateTo(
        _chat.position.maxScrollExtent,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    ref.listen<InterviewState>(interviewControllerProvider, _clearWhenAccepted);
    final InterviewState state = ref.watch(interviewControllerProvider);
    final InterviewQuestion? question = state.question;
    // A new turn, or the summary, is new content to bring into view.
    _keepChatInView(state.transcript.length + (state.done == null ? 0 : 1));

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        if (!state.finished && state.turn > 0) ...<Widget>[
          _TurnBar(turn: state.turn, maxTurns: state.maxTurns),
          SizedBox(height: tokens.spacing.md),
        ],
        Expanded(
          child: ListView(
            controller: _chat,
            padding: EdgeInsets.zero,
            children: <Widget>[
              for (int i = 0; i < state.transcript.length; i++) ...<Widget>[
                _Bubble(text: state.transcript[i].question.text),
                if (state.transcript[i].answer.skipped)
                  _SkippedNote()
                else
                  _Bubble(
                    text: _answerText(state.transcript[i].answer),
                    fromHousehold: true,
                  ),
                if (state.droppedTurns.contains(i)) _DroppedAnswerNote(),
                SizedBox(height: tokens.spacing.md),
              ],
              if (question != null) ...<Widget>[
                // The newest question is the one a screen reader should hear about; earlier turns are read on
                // demand from the transcript.
                _Bubble(text: question.text, announce: true),
                if (question.options.isNotEmpty)
                  Padding(
                    padding: EdgeInsets.only(top: tokens.spacing.sm),
                    child: Wrap(
                      spacing: tokens.spacing.sm,
                      runSpacing: tokens.spacing.sm,
                      children: <Widget>[
                        for (final String option in question.options)
                          FilterChip(
                            label: Text(option),
                            selected: _chosen.contains(option),
                            onSelected: state.pending
                                ? null
                                : (bool isSelected) {
                                    ref.read(hapticsProvider).selectionClick();
                                    setState(() {
                                      if (isSelected) {
                                        _chosen.add(option);
                                      } else {
                                        _chosen.remove(option);
                                      }
                                    });
                                  },
                          ),
                      ],
                    ),
                  ),
              ],
              if (state.pending) _ThinkingRow(),
              if (state.failure case final Object failure)
                _FailureRow(message: failureCopy(failure), onRetry: _retry),
              if (state.done case final InterviewDone done?)
                _SummaryCard(summary: done.summary),
            ],
          ),
        ),
        SizedBox(height: tokens.spacing.md),
        if (state.finished)
          Row(
            children: <Widget>[
              _BackButton(onPressed: widget.onBack),
              SizedBox(width: tokens.spacing.sm),
              Expanded(
                child: FilledButton(
                  onPressed: _confirm,
                  child: const Text('Looks right'),
                ),
              ),
            ],
          )
        else ...<Widget>[
          TextField(
            controller: _composer,
            enabled: !state.pending && question != null,
            minLines: 1,
            maxLines: 3,
            // The backend rejects an answer past its bound, so the field stops there instead of letting a paste
            // turn into a request that can only fail.
            maxLength: InterviewAnswer.maxTextLength,
            buildCounter: _nearLimitCounter,
            textInputAction: TextInputAction.send,
            onSubmitted: (_) => _answer(),
            onChanged: (_) => setState(() {}),
            decoration: const InputDecoration(hintText: 'Type an answer…'),
          ),
          SizedBox(height: tokens.spacing.sm),
          Row(
            children: <Widget>[
              _BackButton(onPressed: state.pending ? null : widget.onBack),
              SizedBox(width: tokens.spacing.sm),
              Expanded(
                child: OutlinedButton(
                  onPressed: question == null || state.pending ? null : _skip,
                  child: const Text('Skip'),
                ),
              ),
              SizedBox(width: tokens.spacing.sm),
              Expanded(
                child: FilledButton(
                  onPressed: question == null || state.pending ? null : _answer,
                  child: const Text('Send'),
                ),
              ),
            ],
          ),
        ],
      ],
    );
  }
}

/// The answer counter, shown only once the household is close to the limit: a count from the first character
/// is noise on a one-line answer, and a silent stop at the limit is worse.
Widget? _nearLimitCounter(
  BuildContext context, {
  required int currentLength,
  required bool isFocused,
  required int? maxLength,
}) {
  if (maxLength == null) return null;
  if (currentLength < maxLength - _counterVisibleFrom) return null;
  return Text(
    '$currentLength/$maxLength',
    style: Theme.of(context).textTheme.bodySmall?.copyWith(
      color: Theme.of(context).colorScheme.onSurfaceVariant,
    ),
  );
}

/// How far from the limit the counter appears.
const double _counterVisibleFrom = 200;

/// One step back through first run. Icon-only so the row still fits a narrow phone at large text next to
/// Skip and Send.
class _BackButton extends StatelessWidget {
  const _BackButton({required this.onPressed});

  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      onPressed: onPressed,
      tooltip: 'Back',
      icon: const Icon(Icons.arrow_back_rounded),
    );
  }
}

/// What the household said, as one line of chat: their free text, their chosen options, or both.
String _answerText(InterviewAnswer answer) {
  final List<String> parts = <String>[
    if (answer.text != null) answer.text!,
    ...answer.options,
  ];
  return parts.join(' · ');
}

/// B's progress bar, kept from the design gate: the household can see how many turns the interview has.
class _TurnBar extends StatelessWidget {
  const _TurnBar({required this.turn, required this.maxTurns});

  final int turn;
  final int maxTurns;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Text(
          'Question $turn of $maxTurns',
          style: theme.textTheme.labelMedium?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        SizedBox(height: tokens.spacing.xs),
        // The count above already says this once; a bar with its own label would say it twice.
        ExcludeSemantics(
          child: ClipRRect(
            borderRadius: BorderRadius.circular(tokens.radius.pill),
            child: LinearProgressIndicator(
              value: (turn / maxTurns).clamp(0, 1),
              minHeight: 4,
            ),
          ),
        ),
      ],
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({
    required this.text,
    this.fromHousehold = false,
    this.announce = false,
  });

  final String text;
  final bool fromHousehold;

  /// Whether a screen reader should read this out as it appears. Only the question on screen is announced.
  final bool announce;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ColorScheme colors = Theme.of(context).colorScheme;
    return Semantics(
      container: true,
      liveRegion: announce,
      label: fromHousehold ? 'You answered: $text' : 'Glean asked: $text',
      child: ExcludeSemantics(child: _bubble(context, tokens, colors)),
    );
  }

  Widget _bubble(BuildContext context, AppTokens tokens, ColorScheme colors) {
    return Align(
      alignment: fromHousehold ? Alignment.centerRight : Alignment.centerLeft,
      child: ConstrainedBox(
        constraints: BoxConstraints(
          maxWidth: MediaQuery.sizeOf(context).width * 0.85,
        ),
        child: Container(
          padding: EdgeInsets.symmetric(
            horizontal: tokens.spacing.md,
            vertical: tokens.spacing.sm,
          ),
          decoration: BoxDecoration(
            color: fromHousehold
                ? colors.primaryContainer
                : colors.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(tokens.radius.md),
          ),
          child: Text(
            text,
            style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: fromHousehold
                  ? colors.onPrimaryContainer
                  : colors.onSurface,
            ),
          ),
        ),
      ),
    );
  }
}

/// Shown under an answer the backend's screening dropped: the household is told plainly, and the interview
/// carries on without it.
class _DroppedAnswerNote extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    return Padding(
      padding: EdgeInsets.only(top: tokens.spacing.xs),
      child: Row(
        children: <Widget>[
          Icon(
            Icons.info_outline_rounded,
            size: 16,
            color: theme.colorScheme.error,
          ),
          SizedBox(width: tokens.spacing.sm),
          Expanded(
            child: Text(
              "Couldn't use that answer",
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.error,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SkippedNote extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    return Semantics(
      container: true,
      label: 'You skipped that question',
      child: ExcludeSemantics(
        child: Padding(
          padding: EdgeInsets.only(top: tokens.spacing.xs),
          child: Align(
            alignment: Alignment.centerRight,
            child: Text(
              'Skipped',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _ThinkingRow extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    return Padding(
      padding: EdgeInsets.only(bottom: tokens.spacing.md),
      child: Row(
        children: <Widget>[
          const SizedBox(
            width: 16,
            height: 16,
            child: CircularProgressIndicator(strokeWidth: 2),
          ),
          SizedBox(width: tokens.spacing.sm),
          Text('Thinking…', style: Theme.of(context).textTheme.bodySmall),
        ],
      ),
    );
  }
}

/// A failed turn, in plain words with a Retry. Nothing about it is internal: the household only has to know
/// the question did not reach Glean.
class _FailureRow extends StatelessWidget {
  const _FailureRow({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    return Padding(
      padding: EdgeInsets.only(bottom: tokens.spacing.md),
      child: Container(
        padding: EdgeInsets.all(tokens.spacing.md),
        decoration: BoxDecoration(
          color: theme.colorScheme.errorContainer,
          borderRadius: BorderRadius.circular(tokens.radius.md),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              message,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onErrorContainer,
              ),
            ),
            SizedBox(height: tokens.spacing.sm),
            Align(
              alignment: Alignment.centerRight,
              child: TextButton(onPressed: onRetry, child: const Text('Retry')),
            ),
          ],
        ),
      ),
    );
  }
}

/// The two-line summary the household confirms. It is the backend's own copy, shown exactly as it arrives.
class _SummaryCard extends StatelessWidget {
  const _SummaryCard({required this.summary});

  final String summary;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    return Container(
      padding: EdgeInsets.all(tokens.spacing.md),
      decoration: BoxDecoration(
        color: theme.colorScheme.primaryContainer,
        borderRadius: BorderRadius.circular(tokens.radius.md),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            "Here's what Glean took from that",
            style: theme.textTheme.titleSmall?.copyWith(
              color: theme.colorScheme.onPrimaryContainer,
            ),
          ),
          SizedBox(height: tokens.spacing.sm),
          Text(
            summary,
            style: theme.textTheme.bodyMedium?.copyWith(
              color: theme.colorScheme.onPrimaryContainer,
            ),
          ),
          SizedBox(height: tokens.spacing.sm),
          Text(
            'You can change any of this later in Settings.',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onPrimaryContainer,
            ),
          ),
        ],
      ),
    );
  }
}

/// How a failed turn reads to the household: plain words, then Retry. Never a status code or an exception.
///
/// A rejected answer is the one failure Retry cannot fix on its own, so its copy names the two ways out: say it
/// differently, or leave the rest with Skip all.
String failureCopy(Object failure) => switch (failure) {
  ApiRateLimitException(:final String userMessage) => userMessage,
  ApiValidationException() =>
    'Glean could not use that answer. Try saying it another way, or skip the '
        'rest with Skip all.',
  ApiTimeoutException() =>
    'Glean took too long to answer. Check your connection and try again.',
  ApiAuthException() => 'Your session has expired. Sign in again to carry on.',
  _ => 'Could not reach Glean. Check your connection and try again.',
};
