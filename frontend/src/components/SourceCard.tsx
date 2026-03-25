import { ExternalLink } from "lucide-react";
import { SOURCE_TYPE_ICONS } from "@/lib/types";
import type { Source } from "@/lib/api";

function isUrl(str: string): boolean {
  return /^https?:\/\//i.test(str);
}

export function SourceCard({
  source,
  showSummary,
  highlighted,
}: {
  source: Source;
  showSummary?: boolean;
  highlighted?: boolean;
}) {
  const icon = SOURCE_TYPE_ICONS[source.source_type] || "📄";
  const score = source.distance != null ? Math.max(0, (1 - source.distance) * 100).toFixed(0) : null;
  const rerankLabel = source.rerank_score != null ? `rerank: ${source.rerank_score.toFixed(2)}` : null;
  const sourceIsUrl = isUrl(source.source);

  return (
    <div
      className={`source-card ${
        highlighted
          ? "ring-1 ring-accent/50 bg-accent/[0.06]"
          : ""
      }`}
    >
      <div className="flex items-start justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className="text-sm flex-shrink-0">{icon}</span>
          {sourceIsUrl ? (
            <a
              href={source.source}
              target="_blank"
              rel="noopener noreferrer"
              className={`font-medium truncate hover:underline inline-flex items-center gap-1 ${
                highlighted ? "text-accent" : "text-foreground"
              }`}
              title={source.source}
            >
              {source.source}
              <ExternalLink className="h-3 w-3 flex-shrink-0 opacity-60" />
            </a>
          ) : (
            <span
              className={`font-medium truncate ${highlighted ? "text-accent" : "text-foreground"}`}
              title={source.source}
            >
              {source.source || source.source_type}
            </span>
          )}
          {highlighted && (
            <span className="text-[9px] uppercase tracking-wider font-semibold text-accent/80 flex-shrink-0">
              Best match
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          {rerankLabel && (
            <span className="text-[10px] font-mono text-emerald-400">{rerankLabel}</span>
          )}
          {score && (
            <span className="text-[10px] font-mono text-accent">{score}%</span>
          )}
        </div>
      </div>
      {/* Always show summary for the highlighted card */}
      {(highlighted || showSummary) && source.summary && (
        <p className={`text-[11px] leading-relaxed mb-2 ${
          highlighted ? "text-muted-foreground line-clamp-4" : "text-muted-foreground line-clamp-3"
        }`}>
          {source.summary}
        </p>
      )}
      {source.tags?.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {source.tags.slice(0, 4).map((tag) => (
            <span
              key={tag}
              className={`px-1.5 py-0.5 rounded-full text-[10px] border ${
                highlighted
                  ? "bg-accent/10 text-accent border-accent/20"
                  : "bg-primary/10 text-primary border-primary/20"
              }`}
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
