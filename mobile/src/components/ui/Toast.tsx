import Toast, { BaseToast, type BaseToastProps } from "react-native-toast-message";
import { theme } from "@/theme";

const toastStyle = {
  borderLeftWidth: 4,
  borderRadius: theme.radius.md,
  paddingVertical: theme.spacing.md,
  backgroundColor: theme.colors.card,
  shadowColor: theme.shadow.card.shadowColor,
  shadowOffset: theme.shadow.card.shadowOffset,
  shadowOpacity: theme.shadow.card.shadowOpacity,
  shadowRadius: theme.shadow.card.shadowRadius,
  elevation: theme.shadow.card.elevation,
};

const text1Style = {
  fontSize: theme.typography.subhead.fontSize,
  fontWeight: theme.typography.headline.fontWeight as "600",
  color: theme.colors.text,
};

const text2Style = {
  fontSize: theme.typography.caption.fontSize,
  color: theme.colors.textSecondary,
};

const toastConfig = {
  success: (props: BaseToastProps) => (
    <BaseToast
      {...props}
      style={{ ...toastStyle, borderLeftColor: theme.colors.success }}
      contentContainerStyle={{ paddingHorizontal: theme.spacing.lg }}
      text1Style={text1Style}
      text2Style={text2Style}
    />
  ),
  error: (props: BaseToastProps) => (
    <BaseToast
      {...props}
      style={{ ...toastStyle, borderLeftColor: theme.colors.warning }}
      contentContainerStyle={{ paddingHorizontal: theme.spacing.lg }}
      text1Style={text1Style}
      text2Style={text2Style}
    />
  ),
  info: (props: BaseToastProps) => (
    <BaseToast
      {...props}
      style={{ ...toastStyle, borderLeftColor: theme.colors.primary }}
      contentContainerStyle={{ paddingHorizontal: theme.spacing.lg }}
      text1Style={text1Style}
      text2Style={text2Style}
    />
  ),
};

export { Toast, toastConfig };
