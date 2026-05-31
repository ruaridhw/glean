class EmptyTextInputError extends Error {
  constructor(message = "Text input cannot be empty") {
    super(message);
    this.name = "EmptyTextInputError";
  }
}

export function normalizeSubmittedText(value: string): string {
  return value.trim();
}

export function toRequiredSubmittedText(value: string): string | null {
  const normalized = normalizeSubmittedText(value);
  return normalized.length > 0 ? normalized : null;
}

export function requireSubmittedText(value: string): string {
  const normalized = toRequiredSubmittedText(value);
  if (!normalized) throw new EmptyTextInputError();
  return normalized;
}
