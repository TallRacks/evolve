import { NativeCard, NativeScreen } from "../../components/NativeScreen";
import { Link } from "expo-router";
export default function MyWork() { return <NativeScreen title="My Work"><NativeCard title="My Tasks" detail="Due today, overdue, blocked, and upcoming work." /><NativeCard title="Approvals" detail="Pending decisions assigned to you." /><NativeCard title="Mentions" detail="Collaboration that needs your attention." /><Link href="/bookings" asChild><NativeCard title="Booking responsibilities" detail="Upcoming assigned bookings and production work." /></Link></NativeScreen>; }
