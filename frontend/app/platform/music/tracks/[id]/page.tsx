import { TrackDetailPage } from "@/components/music-pages";
export default async function Page({params}:{params:Promise<{id:string}>}){return <TrackDetailPage id={(await params).id} platform/>}
