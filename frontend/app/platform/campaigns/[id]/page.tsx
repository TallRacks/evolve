import { CampaignDetailPage } from "@/components/campaign-pages";
export default async function Page({params}:{params:Promise<{id:string}>}){return <CampaignDetailPage id={(await params).id} platform/>}
