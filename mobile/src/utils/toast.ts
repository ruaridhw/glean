import Toast from "react-native-toast-message";

export function showSuccess(message: string) {
  Toast.show({ type: "success", text1: message, visibilityTime: 3000 });
}

export function showError(message: string) {
  Toast.show({ type: "error", text1: message, visibilityTime: 4000 });
}
