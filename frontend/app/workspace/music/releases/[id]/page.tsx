import { ReleaseDetailPage } from "@/components/music-pages";
export default async function Page({params}:{params:Promise<{id:string}>}){return <ReleaseDetailPage id={(await params).id}/>}
