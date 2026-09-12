import { NativeCard, NativeScreen } from "../../components/NativeScreen";
import { useLocalSearchParams } from "expo-router";
export default function BookingDetail() { const { id } = useLocalSearchParams<{ id: string }>(); return <NativeScreen title="Booking"><NativeCard title={id ?? "Booking"} detail="Commercial editing remains web-first; operational data follows Django permissions." /><NativeCard title="Call Sheet" detail="Open the published operational viewer." /></NativeScreen>; }
