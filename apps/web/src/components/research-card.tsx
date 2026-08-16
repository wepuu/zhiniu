import { ArrowUpRight } from "lucide-react";
import { Card } from "./ui/card";

type Note = {
  symbol: string;
  company: string;
  time: string;
  label: string;
  title: string;
  body: string;
  evidence: string;
};

export function ResearchCard({ note }: { note: Note }) {
  return (
    <Card className="group relative overflow-hidden p-5 pl-7 transition hover:-translate-y-0.5 hover:shadow-lg">
      <span className="bg-amber absolute inset-y-0 left-0 w-1.5" />
      <div className="font-data text-slate flex items-center gap-2 text-xs">
        <span className="bg-blue/8 text-blue rounded-md px-2 py-1">
          {note.symbol}
        </span>
        <span>{note.company}</span>
        <span className="ml-auto">{note.time}</span>
      </div>
      <p className="text-amber mt-5 text-[11px] font-semibold uppercase tracking-[0.18em]">
        {note.label}
      </p>
      <h3 className="font-display mt-2 text-xl font-semibold leading-snug">
        {note.title}
      </h3>
      <p className="text-slate mt-2 text-sm leading-6">{note.body}</p>
      <div className="border-ink/10 text-slate mt-5 flex items-center border-t border-dashed pt-3 text-xs">
        <span>{note.evidence}</span>
        <ArrowUpRight className="ml-auto size-4 transition group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
      </div>
    </Card>
  );
}
