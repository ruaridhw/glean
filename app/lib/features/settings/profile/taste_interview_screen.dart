import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:glean/api/api_exception.dart';
import 'package:glean/data/models/household_profile.dart';
import 'package:glean/data/providers/database_providers.dart';
import 'package:glean/data/providers/repository_providers.dart';
import 'package:glean/data/repositories/household_profile_repository.dart';
import 'package:glean/design_system/design_system.dart';
import 'package:glean/features/onboarding/providers/interview_controller.dart';
import 'package:glean/features/onboarding/widgets/onboarding_taste_page.dart'
    show failureCopy;

import 'widgets/profile_facts.dart';

/// One question at a time, with a route-scoped draft and a separate final confirmation.
class TasteInterviewScreen extends ConsumerStatefulWidget {
  const TasteInterviewScreen({required this.baseline, super.key});
  final HouseholdProfile baseline;

  @override
  ConsumerState<TasteInterviewScreen> createState() =>
      _TasteInterviewScreenState();
}

class _TasteInterviewScreenState extends ConsumerState<TasteInterviewScreen> {
  final _answer = TextEditingController();
  final _questionFocus = FocusNode();
  final _chosen = <String>{};
  String? _shown;
  bool _saving = false;
  bool _clearIntent = false;
  String? _saveError;
  bool _conflict = false;
  late String _userId;
  late HouseholdProfile _baseline;

  InterviewController get _controller =>
      ref.read(retakeInterviewControllerProvider.notifier);

  @override
  void initState() {
    super.initState();
    _userId = ref.read(currentUserIdProvider);
    _baseline = widget.baseline;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) unawaited(_controller.beginRetake(widget.baseline));
    });
  }

  @override
  void dispose() {
    _answer.dispose();
    _questionFocus.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    if (_clearIntent && _answer.text.trim().isEmpty && _chosen.isEmpty) {
      await _controller.clearAnswer();
    } else if (_answer.text.trim().isEmpty && _chosen.isEmpty) {
      await _controller.skip();
    } else {
      await _controller.answer(text: _answer.text, options: _chosen.toList());
    }
  }

  Future<void> _confirm() async {
    if (_saving || _conflict) return;
    setState(() {
      _saving = true;
      _saveError = null;
    });
    final saved = await _controller.confirm();
    if (!mounted) return;
    if (saved) {
      Navigator.of(context).pop();
      return;
    }
    final error = ref.read(retakeInterviewControllerProvider).failure;
    setState(() {
      _saving = false;
      _conflict = error is ProfileInterviewConflict;
      _saveError = _conflict
          ? 'Your profile changed during this interview. Start again to review the latest answers.'
          : 'Could not save your profile. Your saved profile is unchanged. Try again.';
    });
  }

  Future<void> _restart() async {
    final latest = await ref
        .read(householdProfileRepositoryProvider)
        .get(_userId);
    if (!mounted) return;
    setState(() {
      _conflict = false;
      _saveError = null;
      _shown = null;
      _baseline = latest ?? const HouseholdProfile();
    });
    await _controller.beginRetake(_baseline);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(retakeInterviewControllerProvider);
    final userId = ref.watch(currentUserIdProvider);
    if (userId != _userId) {
      return Scaffold(
        appBar: AppBar(title: const Text('Taste interview')),
        body: const Center(
          child: Text(
            'Your account changed. Close this interview and start again.',
          ),
        ),
      );
    }
    final question = state.question;
    if (question != null && _shown != question.id) {
      _shown = question.id;
      final restored = _controller.draftAnswer(question);
      _clearIntent = restored?.clear ?? false;
      _chosen
        ..clear()
        ..addAll(restored?.options ?? const <String>[]);
      _answer.text = restored == null || restored.skipped
          ? _controller.prefill(question)
          : restored.text ?? '';
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) _questionFocus.requestFocus();
      });
    }
    final tokens = context.tokens;
    final text = Theme.of(context).textTheme;
    final done = state.done;
    final failure = state.failure;
    final children = <Widget>[
      if (state.droppedTurns.isNotEmpty ||
          (done?.unappliedFields.isNotEmpty ?? false))
        Semantics(
          liveRegion: true,
          child: const Text(
            "Couldn't use that answer; kept your previous preference. Review your answers to try again.",
          ),
        ),
    ];
    if (done != null) {
      children.addAll(<Widget>[
        Text('Does this sound like you?', style: text.headlineSmall),
        const Text('Your revised facts, before they replace the saved ones.'),
        for (final field in done.updatedFields)
          if (_emptyValue(done.profile.toJson()[field]) &&
              !_emptyValue(_baseline.toJson()[field]))
            Text(
              'Will be cleared: ${_fieldLabel(field)}. Nothing has been removed yet.',
            ),
        ProfileFacts(profile: done.profile, memoryTitle: 'Kept unchanged'),
        const Text(
          'Memory notes and dismissed notes stay unchanged. Cancel keeps your saved profile exactly as it was.',
        ),
      ]);
    } else if (question != null) {
      children.addAll(<Widget>[
        Text(
          'Question ${state.turn} of ${state.maxTurns}',
          style: text.labelMedium,
        ),
        LinearProgressIndicator(value: state.turn / state.maxTurns),
        Focus(
          focusNode: _questionFocus,
          child: Semantics(
            header: true,
            liveRegion: true,
            child: Text(question.text, style: text.titleLarge),
          ),
        ),
        Text(
          _controller.draftAnswer(question) != null
              ? 'Your draft answer'
              : _controller.prefill(question).isEmpty
              ? 'Your answer'
              : 'Prefilled from your saved profile',
          style: text.labelMedium,
        ),
        if (_clearIntent)
          const Text(
            'This answer is marked to be cleared. Continue keeps that change; Skip keeps the saved facts.',
          ),
        TextField(
          controller: _answer,
          onChanged: (value) {
            if (_clearIntent && value.isNotEmpty) {
              setState(() => _clearIntent = false);
            }
          },
          enabled: !state.pending,
          minLines: 4,
          maxLines: 8,
          maxLength: 2000,
          decoration: const InputDecoration(hintText: 'Your answer…'),
          onSubmitted: (_) {
            if (!state.pending) unawaited(_send());
          },
        ),
        if (question.options.isNotEmpty)
          Wrap(
            spacing: tokens.spacing.sm,
            runSpacing: tokens.spacing.sm,
            children: <Widget>[
              for (final option in question.options)
                FilterChip(
                  label: Text(option),
                  selected: _chosen.contains(option),
                  onSelected: state.pending
                      ? null
                      : (selected) => setState(() {
                          if (selected) {
                            _clearIntent = false;
                            _chosen.add(option);
                          } else {
                            _chosen.remove(option);
                          }
                        }),
                ),
            ],
          ),
        const Text(
          'These are saved facts, not your original answer. Skip or an empty answer keeps your saved facts.',
        ),
        TextButton(
          onPressed: state.pending
              ? null
              : () => unawaited(_controller.clearAnswer()),
          child: const Text('Clear this answer'),
        ),
        const Text(
          'Clearing only changes this draft. Review removals before saving.',
        ),
      ]);
    }
    if (state.pending) {
      children.add(const Center(child: CircularProgressIndicator()));
    }
    if (failure != null && done == null) {
      children.addAll(<Widget>[
        Semantics(liveRegion: true, child: Text(failureCopy(failure))),
        if (failure is! ApiValidationException)
          OutlinedButton(
            onPressed: state.pending
                ? null
                : () => unawaited(_controller.retry()),
            child: const Text('Retry'),
          ),
      ]);
    }
    return PopScope(
      canPop: !_saving,
      child: Scaffold(
        appBar: AppBar(
          automaticallyImplyLeading: false,
          title: const Text('Taste interview'),
          leadingWidth: 88,
          leading: TextButton(
            onPressed: _saving ? null : () => Navigator.of(context).pop(),
            child: const Text('Cancel'),
          ),
        ),
        body: SafeArea(
          child: Column(
            children: <Widget>[
              Expanded(
                child: ListView(
                  padding: EdgeInsets.all(tokens.spacing.lg),
                  children: <Widget>[
                    for (final child in children) ...<Widget>[
                      child,
                      SizedBox(height: tokens.spacing.md),
                    ],
                  ],
                ),
              ),
              Padding(
                padding: EdgeInsets.all(tokens.spacing.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: <Widget>[
                    if (_saveError != null)
                      Semantics(
                        liveRegion: true,
                        child: Text(
                          _saveError!,
                          style: text.bodyMedium?.copyWith(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                      ),
                    if (done != null) ...<Widget>[
                      if (_conflict)
                        FilledButton(
                          onPressed: () => unawaited(_restart()),
                          child: const Text('Start again'),
                        )
                      else
                        FilledButton(
                          onPressed: _saving
                              ? null
                              : () => unawaited(_confirm()),
                          child: Text(_saving ? 'Saving…' : 'Save profile'),
                        ),
                      if (!_saving && !_conflict)
                        OutlinedButton(
                          onPressed: () {
                            setState(() {
                              _shown = null;
                              _saveError = null;
                            });
                            _controller.reviewAnswers();
                          },
                          child: const Text('Review answers again'),
                        ),
                    ] else if (question != null)
                      Wrap(
                        spacing: tokens.spacing.sm,
                        runSpacing: tokens.spacing.sm,
                        alignment: WrapAlignment.end,
                        children: <Widget>[
                          if (_controller.canGoBack)
                            OutlinedButton(
                              onPressed: state.pending
                                  ? null
                                  : () {
                                      setState(() => _shown = null);
                                      _controller.back();
                                    },
                              child: const Text('Back'),
                            ),
                          OutlinedButton(
                            onPressed: state.pending
                                ? null
                                : () => unawaited(_controller.skip()),
                            child: const Text('Skip'),
                          ),
                          FilledButton(
                            onPressed: state.pending
                                ? null
                                : () => unawaited(_send()),
                            child: const Text('Continue'),
                          ),
                        ],
                      ),
                    SizedBox(height: tokens.spacing.sm),
                    Text(
                      'Saved profile unchanged until you confirm.',
                      style: text.bodySmall,
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

bool _emptyValue(Object? value) =>
    value == null || value == '' || (value is List && value.isEmpty);
String _fieldLabel(String field) => switch (field) {
  'favourite_meals' => 'Favourite dinners',
  'loved_ingredients' => 'Loved ingredients',
  'disliked_ingredients' => 'Never on the plan',
  'cuisines_liked' => 'Liked cuisines',
  'cuisines_avoided' => 'Avoided cuisines',
  'protein_targets' => 'Protein targets',
  'spice_tolerance' => 'Spice tolerance',
  'habits' => 'Your week',
  'household' => 'At the table',
  _ => field,
};
