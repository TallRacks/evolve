import { TaskDetailPage } from "@/components/workflow-pages";

export default async function Page({params}:{params:Promise<{id:string}>}){return <TaskDetailPage id={(await params).id}/>}
