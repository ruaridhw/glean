// mobile/app/(tabs)/settings/index.tsx
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { router } from 'expo-router';
import { signOut } from '@/auth/cognito';

export default function SettingsScreen() {
  async function handleSignOut() {
    await signOut();
    router.replace('/sign-in');
  }

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Settings</Text>
      <Pressable style={styles.button} onPress={handleSignOut}>
        <Text style={styles.buttonText}>Sign out</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 24, backgroundColor: '#fff' },
  heading: { fontSize: 24, fontWeight: '700', marginBottom: 32 },
  button: { backgroundColor: '#e63946', borderRadius: 8, padding: 14, alignItems: 'center' },
  buttonText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});
