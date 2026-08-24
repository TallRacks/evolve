import { RolloutDetailPage } from "@/components/campaign-pages";
export default async function Page({params}:{params:Promise<{id:string}>}){return <RolloutDetailPage id={(await params).id}/>}
