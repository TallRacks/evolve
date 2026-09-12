import { PropsWithChildren } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

export function NativeScreen({ title, children }: PropsWithChildren<{ title: string }>) {
  return <SafeAreaView style={styles.safe}><ScrollView contentContainerStyle={styles.content}><Text accessibilityRole="header" style={styles.title}>{title}</Text>{children}</ScrollView></SafeAreaView>;
}

export function NativeCard({ title, detail, onPress }: { title: string; detail?: string; onPress?: () => void }) {
  const body = <View style={styles.card}><Text style={styles.cardTitle}>{title}</Text>{detail ? <Text style={styles.detail}>{detail}</Text> : null}</View>;
  return onPress ? <Pressable accessibilityRole="button" accessibilityLabel={title} onPress={onPress}>{body}</Pressable> : body;
}

export function NativeButton({ label, onPress }: { label: string; onPress: () => void }) {
  return <Pressable accessibilityRole="button" style={styles.button} onPress={onPress}><Text style={styles.buttonText}>{label}</Text></Pressable>;
}

const styles = StyleSheet.create({ safe: { flex: 1, backgroundColor: "#f7f8fa" }, content: { padding: 20, gap: 14 }, title: { color: "#111827", fontSize: 28, fontWeight: "700", marginBottom: 6 }, card: { backgroundColor: "white", borderRadius: 14, padding: 16, gap: 6, borderWidth: 1, borderColor: "#e5e7eb" }, cardTitle: { color: "#111827", fontSize: 16, fontWeight: "600" }, detail: { color: "#667085", fontSize: 14 }, button: { backgroundColor: "#111827", borderRadius: 12, minHeight: 48, justifyContent: "center", alignItems: "center", paddingHorizontal: 16 }, buttonText: { color: "white", fontWeight: "700" } });
