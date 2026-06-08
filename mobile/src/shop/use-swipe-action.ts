const DEFAULT_ACTION_THRESHOLD = 48;
const DEFAULT_VELOCITY_THRESHOLD = 0.75;

interface SwipeTranslation {
  translationX: number;
  translationY: number;
  velocityX?: number;
}

export function shouldRunSwipeAction(
  { translationX, translationY, velocityX = 0 }: SwipeTranslation,
  threshold = DEFAULT_ACTION_THRESHOLD,
): boolean {
  const isMostlyHorizontal = Math.abs(translationX) > Math.abs(translationY);
  const hasDistance = translationX <= -threshold;
  const hasMomentum = translationX < 0 && velocityX <= -DEFAULT_VELOCITY_THRESHOLD;
  return isMostlyHorizontal && (hasDistance || hasMomentum);
}
