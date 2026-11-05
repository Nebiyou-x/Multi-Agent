import HomePage from "@/components/HomePage";
import { getDocsIndex } from "@/lib/docs";
import { listTraces } from "@/lib/traces";

export default function Page() {
  return <HomePage docs={getDocsIndex()} traces={listTraces()} />;
}
