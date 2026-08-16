import { AlertTriangle, Inbox, LoaderCircle } from "lucide-react";
import { Card } from "./card";

export function EmptyState() {
  return (
    <Card className="grid min-h-48 place-items-center p-8 text-center">
      <div>
        <Inbox className="text-slate mx-auto mb-3" />
        <p className="font-medium">还没有研究记录</p>
        <p className="text-slate mt-1 text-sm">
          添加自选股后，变化线索会集中显示在这里。
        </p>
      </div>
    </Card>
  );
}

export function LoadingState() {
  return (
    <div className="text-slate flex items-center gap-2 text-sm" role="status">
      <LoaderCircle className="size-4 animate-spin" />
      正在整理研究数据…
    </div>
  );
}

export function ErrorState() {
  return (
    <Card className="border-risk/30 flex items-start gap-3 p-5">
      <AlertTriangle className="text-risk mt-0.5 size-5" />
      <div>
        <p className="font-medium">数据暂时不可用</p>
        <p className="text-slate text-sm">
          请检查连接后重试；已展示的数据不会丢失。
        </p>
      </div>
    </Card>
  );
}
