import 'package:flutter/material.dart';
import 'package:glean/design_system/design_system.dart';

import '../../settings/settings_presentation.dart';
import '../../settings/widgets/dietary_preferences_card.dart';
import '../../settings/widgets/preference_slider_card.dart';

/// The whole basics page: dinners and servings side by side as the two numbers
/// that matter, then the dietary flags behind a disclosure so a household with
/// no restrictions can finish without opening it.
class OnboardingBasicsPage extends StatelessWidget {
  const OnboardingBasicsPage({
    required this.dinners,
    required this.servings,
    required this.dietaryFlags,
    required this.onDinnersChanged,
    required this.onServingsChanged,
    required this.onDietaryFlagToggled,
    super.key,
  });

  final int dinners;
  final int servings;
  final Set<String> dietaryFlags;
  final ValueChanged<int> onDinnersChanged;
  final ValueChanged<int> onServingsChanged;
  final void Function(String flag, bool isSelected) onDietaryFlagToggled;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    return SingleChildScrollView(
      padding: EdgeInsets.symmetric(horizontal: tokens.spacing.xl),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          SizedBox(height: tokens.spacing.sm),
          Text('The basics', style: theme.textTheme.headlineLarge),
          SizedBox(height: tokens.spacing.sm),
          Text(
            'Two numbers now. Dietary preferences are optional and there if '
            'they apply.',
            style: theme.textTheme.bodyMedium,
          ),
          SizedBox(height: tokens.spacing.xl),
          IntrinsicHeight(
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: <Widget>[
                Expanded(
                  child: _NumberTile(
                    label: 'Dinners per week',
                    valueKey: const ValueKey<String>('onboarding.dinnersValue'),
                    sliderKey: const Key('onboarding.dinnersSlider'),
                    value: dinners,
                    unit: dinners == 1 ? 'dinner a week' : 'dinners a week',
                    min: SettingsOptionRanges.dinnersPerWeek.min,
                    max: SettingsOptionRanges.dinnersPerWeek.max,
                    onChanged: onDinnersChanged,
                  ),
                ),
                SizedBox(width: tokens.spacing.md),
                Expanded(
                  child: _NumberTile(
                    label: 'Servings',
                    valueKey: const ValueKey<String>(
                      'onboarding.servingsValue',
                    ),
                    sliderKey: const Key('onboarding.servingsSlider'),
                    value: servings,
                    unit: servings == 1 ? 'person' : 'people',
                    min: SettingsOptionRanges.defaultServings.min,
                    max: SettingsOptionRanges.defaultServings.max,
                    onChanged: onServingsChanged,
                  ),
                ),
              ],
            ),
          ),
          SizedBox(height: tokens.spacing.xl),
          _DietaryDisclosure(
            selected: dietaryFlags,
            onToggle: onDietaryFlagToggled,
          ),
        ],
      ),
    );
  }
}

/// One number and its slider. Label, value and unit repeat the shape Settings
/// uses, but the value is the biggest object on the page — the part of the old
/// one-question-per-screen flow worth keeping.
class _NumberTile extends StatelessWidget {
  const _NumberTile({
    required this.label,
    required this.valueKey,
    required this.sliderKey,
    required this.value,
    required this.unit,
    required this.min,
    required this.max,
    required this.onChanged,
  });

  final String label;
  final Key valueKey;
  final Key sliderKey;
  final int value;
  final String unit;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    return Card(
      child: Padding(
        padding: EdgeInsets.all(tokens.spacing.md),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisSize: MainAxisSize.min,
          children: <Widget>[
            Text(
              label.toUpperCase(),
              style: theme.textTheme.labelSmall,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
            SizedBox(height: tokens.spacing.xs),
            Text(
              '$value',
              key: valueKey,
              style: theme.textTheme.headlineLarge?.copyWith(
                fontSize: 40,
                height: 1,
                letterSpacing: -1.5,
                // The chosen value is the one thing the old one-question
                // screens got right: it is the loudest object on the page.
                color: theme.colorScheme.primary,
              ),
            ),
            Text(unit, style: theme.textTheme.bodySmall),
            SizedBox(height: tokens.spacing.sm),
            IntegerSliderControl(
              value: value,
              min: min,
              max: max,
              onChanged: onChanged,
              onCommitted: onChanged,
              sliderKey: sliderKey,
            ),
          ],
        ),
      ),
    );
  }
}

/// The dietary-flag section, collapsed to one row that still reports how many
/// flags are on. Same chips, order and widget as Settings once open.
class _DietaryDisclosure extends StatefulWidget {
  const _DietaryDisclosure({required this.selected, required this.onToggle});

  final Set<String> selected;
  final void Function(String flag, bool isSelected) onToggle;

  @override
  State<_DietaryDisclosure> createState() => _DietaryDisclosureState();
}

class _DietaryDisclosureState extends State<_DietaryDisclosure> {
  bool _open = false;

  @override
  Widget build(BuildContext context) {
    final AppTokens tokens = context.tokens;
    final ThemeData theme = Theme.of(context);
    final int count = widget.selected.length;
    return Card(
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Semantics(
            container: true,
            button: true,
            expanded: _open,
            label: 'Dietary preferences, $count selected',
            child: ExcludeSemantics(
              child: InkWell(
                onTap: () => setState(() => _open = !_open),
                child: Padding(
                  padding: EdgeInsets.all(tokens.spacing.md),
                  child: Row(
                    children: <Widget>[
                      Icon(
                        _open
                            ? Icons.expand_more_rounded
                            : Icons.chevron_right_rounded,
                        size: 20,
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                      SizedBox(width: tokens.spacing.sm),
                      Expanded(
                        child: Text(
                          'Dietary preferences',
                          style: theme.textTheme.titleMedium,
                        ),
                      ),
                      Text('$count selected', style: theme.textTheme.bodySmall),
                    ],
                  ),
                ),
              ),
            ),
          ),
          if (_open)
            Padding(
              padding: EdgeInsets.fromLTRB(
                tokens.spacing.md,
                0,
                tokens.spacing.md,
                tokens.spacing.md,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: <Widget>[
                  Text(
                    'Pick only what applies. Glean won’t plan a meal that '
                    'breaks these.',
                    style: theme.textTheme.bodySmall,
                  ),
                  SizedBox(height: tokens.spacing.md),
                  DietaryFlagsControl(
                    selected: widget.selected,
                    onToggle: widget.onToggle,
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
