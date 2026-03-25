import { SOURCE_TYPE_ICONS } from "@/lib/types";
import type { Source } from "@/lib/api";

export function SourceCard({ source, showSummary }: { source: Source; showSummary?: boolean }) {
  const icon = SOURCE_TYPE_ICONS[source.source_type] || "📄";
  const score = source.distance != null ? Math.max(0, (1 - source.distance) * 100).toFixed(0) : null;

  return (
    <div className="source-card">
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-sm flex-shrink-0">{icon}</span>
          <span className="text-foreground font-medium truncate">
            {source.source || source.source_type}
          </span>
        </div>
        {score && (
          <span className="text-[10px] font-mono text-accent flex-shrink-0">{score}%</span>
        )}
      </div>
      {showSummary && source.summary && (
        <p className="text-muted-foreground text-[11px] leading-relaxed line-clamp-3 mb-2">
          {source.summary}
        </p>
      )}
      {source.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {source.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className="px-1.5 py-0.5 rounded-full text-[10px] bg-primary/10 text-primary border border-primary/20"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
