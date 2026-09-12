import { useState } from "react";
import { Alert, TextInput } from "react-native";
import { NativeButton, NativeScreen } from "../components/NativeScreen";
import { useAuth } from "../providers/AuthProvider";

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [saving, setSaving] = useState(false);
  async function submit() { setSaving(true); try { await login(email.trim(), password); } catch { Alert.alert("Sign in failed", "Check your credentials and try again."); } finally { setSaving(false); } }
  return <NativeScreen title="Sign in"><TextInput accessibilityLabel="Email" autoCapitalize="none" keyboardType="email-address" placeholder="Email" value={email} onChangeText={setEmail} style={{ backgroundColor: "white", borderColor: "#d0d5dd", borderWidth: 1, borderRadius: 12, padding: 14, minHeight: 52 }} /><TextInput accessibilityLabel="Password" placeholder="Password" secureTextEntry value={password} onChangeText={setPassword} style={{ backgroundColor: "white", borderColor: "#d0d5dd", borderWidth: 1, borderRadius: 12, padding: 14, minHeight: 52 }} /><NativeButton label={saving ? "Signing in…" : "Sign in"} onPress={submit} /></NativeScreen>;
}
