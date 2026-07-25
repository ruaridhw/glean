/// Pure presentation helpers shared by the intake screens, ported from
/// `mobile/src/intake/presentation.ts`.
library;

const double _lowConfidenceThreshold = 0.7;

/// Whether an AI-extracted review row is uncertain enough to flag for a
/// manual check (the "CHECK" badge on a review row).
bool isLowConfidence(double confidence) => confidence < _lowConfidenceThreshold;
