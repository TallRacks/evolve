import { NativeCard, NativeScreen } from "../components/NativeScreen";
import { Link } from "expo-router";
export default function Artists() { return <NativeScreen title="Artists"><Link href="/artist/example" asChild><NativeCard title="Artist list" detail="Team, bookings, travel, music, campaigns, documents, and tasks." /></Link></NativeScreen>; }
