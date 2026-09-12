import { NativeButton, NativeScreen } from "../../components/NativeScreen";
import { Alert } from "react-native";
export default function Create() { const actions = ["Task", "Booking", "Contact", "Production", "Travel", "Release", "Calendar Event"]; return <NativeScreen title="Create"><NativeButton label="Choose an action" onPress={() => Alert.alert("Create", actions.join("  •  "))} />{actions.map((action) => <NativeButton key={action} label={action} onPress={() => Alert.alert(action, "This opens the permission-aware native form when the API is available.")} />)}</NativeScreen>; }
