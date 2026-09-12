import * as SecureStore from "expo-secure-store";

// Reserved for the reviewed native credential design. No production auth flow
// calls this module until the security decision gate is approved.
const SESSION_KEY = "evolve.native.session.pending-review";

export async function clearPendingNativeSession(): Promise<void> {
  await SecureStore.deleteItemAsync(SESSION_KEY);
}
