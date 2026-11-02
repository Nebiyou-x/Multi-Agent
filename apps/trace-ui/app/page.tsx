import HomePage from "@/components/HomePage";
import { getDocsIndex } from "@/lib/docs";

export default function Page() {
  return <HomePage docs={getDocsIndex()} />;
}
