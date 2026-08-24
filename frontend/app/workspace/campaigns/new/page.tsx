import { CampaignCreatePage } from "@/components/campaign-pages";
export default async function Page({searchParams}:{searchParams:Promise<{release?:string}>}){return <CampaignCreatePage releaseId={(await searchParams).release}/>}
