import { ArtistDetailPage } from "@/components/artist-pages"; export default async function Page({params}:{params:Promise<{id:string}>}){return <ArtistDetailPage id={(await params).id}/>;}
