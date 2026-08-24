import { PublishedCallSheetPage } from "@/components/call-sheet-pages";
export default async function Page({params}:{params:Promise<{versionId:string}>}){return <PublishedCallSheetPage versionId={(await params).versionId}/>}
