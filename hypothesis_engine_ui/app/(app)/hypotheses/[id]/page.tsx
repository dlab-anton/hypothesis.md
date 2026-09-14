"use client";

import { useParams } from "next/navigation";
import { HypothesisDetail } from "@/components/hypothesis/HypothesisDetail";

export default function HypothesisDetailPage() {
  const params = useParams();
  const id = params.id as string;

  return <HypothesisDetail id={id} />;
}
