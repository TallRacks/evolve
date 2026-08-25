import { TravelEditPage } from "@/components/travel-pages";
export default async function Page({params}:{params:Promise<{id:string}>}){return <TravelEditPage id={(await params).id}/>}
