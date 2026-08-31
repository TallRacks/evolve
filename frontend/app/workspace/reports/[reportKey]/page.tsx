import { ReportPage } from "@/components/reporting-pages";

export default async function Page({ params }: { params: Promise<{ reportKey: string }> }) {
  const { reportKey } = await params;
  return <ReportPage reportKey={reportKey} />;
}
