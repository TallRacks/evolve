import { CanonicalCallSheetPreviewPage } from "@/components/call-sheet-pages";
export default async function Page({params}:{params:Promise<{versionId:string}>}){return <CanonicalCallSheetPreviewPage versionId={(await params).versionId}/>}
