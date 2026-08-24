import { CallSheetEditorPage } from "@/components/call-sheet-pages";
export default async function Page({params}:{params:Promise<{versionId:string}>}){return <CallSheetEditorPage versionId={(await params).versionId}/>}
