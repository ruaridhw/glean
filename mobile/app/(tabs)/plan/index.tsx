import { View, Text, StyleSheet } from 'react-native';
export default function PlanScreen() {
  return <View style={s.c}><Text style={s.t}>Plan</Text></View>;
}
const s = StyleSheet.create({ c: { flex: 1, alignItems: 'center', justifyContent: 'center' }, t: { fontSize: 24 } });
