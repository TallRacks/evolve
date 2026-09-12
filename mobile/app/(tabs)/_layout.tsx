import { Redirect, Tabs } from "expo-router";
import { useAuth } from "../../providers/AuthProvider";

export default function TabsLayout() {
  const { ready, authenticated } = useAuth();
  if (!ready) return null;
  if (!authenticated) return <Redirect href="/login" />;
  return <Tabs screenOptions={{ tabBarAccessibilityLabel: "Evolve navigation", headerShown: false }}><Tabs.Screen name="index" options={{ title: "Home" }} /><Tabs.Screen name="my-work" options={{ title: "My Work" }} /><Tabs.Screen name="create" options={{ title: "Create" }} /><Tabs.Screen name="inbox" options={{ title: "Inbox" }} /><Tabs.Screen name="more" options={{ title: "More" }} /></Tabs>;
}
