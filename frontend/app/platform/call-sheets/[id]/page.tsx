import { PlatformCallSheetDetailPage } from "@/components/call-sheet-pages";
export default async function Page({params}:{params:Promise<{id:string}>}){return <PlatformCallSheetDetailPage id={(await params).id}/>}
