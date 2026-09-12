import { NativeCard, NativeScreen } from "../../components/NativeScreen";
import { Link } from "expo-router";

export default function Home() {
  return <NativeScreen title="Today"><NativeCard title="Needs attention" detail="Your operational priorities appear here from Evolve." /><Link href="/my-work" asChild><NativeCard title="My Work" detail="Tasks, approvals, mentions, bookings, and production responsibilities." /></Link><Link href="/bookings" asChild><NativeCard title="Upcoming bookings" detail="Open the authorized booking queue." /></Link><Link href="/copilot" asChild><NativeCard title="Ask Copilot" detail="Questions and allowed actions use the same server gateway." /></Link></NativeScreen>;
}
