import { NativeCard, NativeScreen } from "../components/NativeScreen";
import { Link } from "expo-router";
export default function Bookings() { return <NativeScreen title="Bookings"><Link href="/booking/example" asChild><NativeCard title="Priority queue" detail="Days out, readiness, team, contacts, operations, and documents." /></Link></NativeScreen>; }
