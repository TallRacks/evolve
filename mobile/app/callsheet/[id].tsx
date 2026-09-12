import { NativeCard, NativeScreen } from "../../components/NativeScreen";
import { useLocalSearchParams } from "expo-router";
export default function CallSheet() { const { id } = useLocalSearchParams<{ id: string }>(); return <NativeScreen title="Call Sheet"><NativeCard title={id ?? "Published Call Sheet"} detail="Team • venue • schedule • contacts • travel • accommodation • production • hospitality • notes" /></NativeScreen>; }
