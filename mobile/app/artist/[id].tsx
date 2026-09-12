import { NativeCard, NativeScreen } from "../../components/NativeScreen";
import { useLocalSearchParams } from "expo-router";
export default function ArtistDetail() { const { id } = useLocalSearchParams<{ id: string }>(); return <NativeScreen title="Artist"><NativeCard title={id ?? "Artist"} detail="Authorized Artist 360 sections are loaded from Django." /></NativeScreen>; }
