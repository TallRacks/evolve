import { NativeButton, NativeCard, NativeScreen } from "../../components/NativeScreen";
import { useLocalSearchParams } from "expo-router";
export default function TaskDetail() { const { id } = useLocalSearchParams<{ id: string }>(); return <NativeScreen title="Task"><NativeCard title={id ?? "Task"} detail="Status, priority, due date, checklist, related entity, comments, and assignee are server-authorized." /><NativeButton label="Complete task" onPress={() => {}} /></NativeScreen>; }
