import { getChannelColor } from "@/lib/constants";
import { Badge } from "@/components/ui/badge";

export function ChannelBadge({ channel }: { channel: string }) {
  const { text, bg } = getChannelColor(channel);
  return (
    <Badge variant="outline" className={`rounded-full text-[10px] px-2 py-0.5 ${text} ${bg} border-transparent`}>
      #{channel}
    </Badge>
  );
}
