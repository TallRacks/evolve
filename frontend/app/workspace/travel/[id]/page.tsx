import { TravelDetailPage } from "@/components/travel-pages";
export default async function Page({params}:{params:Promise<{id:string}>}){return <TravelDetailPage id={(await params).id}/>}
