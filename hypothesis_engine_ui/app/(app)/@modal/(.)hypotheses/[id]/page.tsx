"use client";

import { useParams, useRouter } from "next/navigation";
import { HypothesisDetail } from "@/components/hypothesis/HypothesisDetail";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function HypothesisModal() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  return (
    <Dialog
      defaultOpen
      onOpenChange={(open) => {
        if (!open) router.back();
      }}
    >
      <DialogContent className="max-w-3xl h-[85vh] p-0 gap-0">
        <DialogTitle className="sr-only">Hypothesis detail</DialogTitle>
        <ScrollArea className="h-full px-6 pb-6 pt-10">
          <HypothesisDetail id={id} modal />
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}
