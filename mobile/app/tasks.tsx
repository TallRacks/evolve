import { NativeCard, NativeScreen } from "../components/NativeScreen";
import { Link } from "expo-router";
export default function Tasks() { return <NativeScreen title="Tasks"><Link href="/task/example" asChild><NativeCard title="Assigned tasks" detail="Real API data loads here after approved native authentication." /></Link><NativeCard title="Due today" detail="No development fixture is presented as production data." /></NativeScreen>; }
