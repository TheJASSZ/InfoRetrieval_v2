import { useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { ChevronDown, ChevronRight, RefreshCw, BarChart3 } from "lucide-react";
import type { ChatMessage as ChatMessageType } from "@/lib/types";
import { SOURCE_TYPE_ICONS } from "@/lib/types";
import { SourceCard } from "./SourceCard";

export function ChatMessageBubble({ message }: { message: ChatMessageType }) {
  const [sourcesOpen, setSourcesOpen] = useState(false);
  const isUser = message.role === "user";
  const sources = message.sources || [];
  const searchResults = message.searchResults || [];

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: "easeOut" }}
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}
    >
      <div className={`${isUser ? "max-w-[75%]" : "max-w-[85%]"}`}>
        <div
          className={`message-bubble ${
            isUser
              ? "gradient-accent text-primary-foreground rounded-br-md"
              : "glass rounded-bl-md"
          }`}
        >
          {isUser ? (
            <p className="text-sm whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="prose prose-sm prose-invert max-w-none text-sm
              prose-p:leading-relaxed prose-p:mb-2
              prose-code:bg-white/[0.06] prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-accent prose-code:font-mono prose-code:text-xs
              prose-pre:bg-white/[0.04] prose-pre:border prose-pre:border-white/[0.06] prose-pre:rounded-lg
              prose-headings:gradient-text prose-headings:font-semibold
              prose-a:text-accent prose-a:no-underline hover:prose-a:underline
              prose-strong:text-foreground
              prose-ul:my-1 prose-li:my-0">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {/* CRAG + Evaluation badges */}
        {!isUser && (message.cragTriggered || message.evaluation) && (
          <div className="flex items-center gap-2 mt-1.5 px-1">
            {message.cragTriggered && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                <RefreshCw className="h-2.5 w-2.5" />
                CRAG rewrite
              </span>
            )}
            {message.evaluation && (
              <span className="inline-flex items-center gap-1 text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <BarChart3 className="h-2.5 w-2.5" />
                Quality: {(message.evaluation.overall * 100).toFixed(0)}%
                {" "}(F:{(message.evaluation.faithfulness * 100).toFixed(0)}
                {" "}R:{(message.evaluation.answer_relevancy * 100).toFixed(0)}
                {" "}P:{(message.evaluation.context_precision * 100).toFixed(0)})
              </span>
            )}
          </div>
        )}

        {/* Sources: top match highlighted, rest collapsible */}
        {sources.length > 0 && (
          <div className="mt-2">
            {/* Top source - always visible */}
            <div className="mt-1.5">
              <SourceCard source={sources[0]} highlighted />
            </div>

            {/* Remaining sources - collapsible */}
            {sources.length > 1 && (
              <>
                <button
                  onClick={() => setSourcesOpen(!sourcesOpen)}
                  className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors mt-2"
                >
                  {sourcesOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  <span>{sources.length - 1} more source{sources.length - 1 !== 1 ? "s" : ""}</span>
                </button>
                {sourcesOpen && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2"
                  >
                    {sources.slice(1).map((s, i) => (
                      <SourceCard key={s.id || i} source={s} />
                    ))}
                  </motion.div>
                )}
              </>
            )}
          </div>
        )}

        {/* Search Results: top match highlighted */}
        {searchResults.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex flex-col gap-2 mt-3"
          >
            <SourceCard source={searchResults[0]} showSummary highlighted />
            {searchResults.length > 1 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {searchResults.slice(1).map((r, i) => (
                  <SourceCard key={r.id || i} source={r} showSummary />
                ))}
              </div>
            )}
          </motion.div>
        )}

        <div className="text-[10px] text-muted-foreground/50 mt-1 px-1">
          {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
        </div>
      </div>
    </motion.div>
  );
}

export function TypingIndicator() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex justify-start mb-4"
    >
      <div className="glass message-bubble rounded-bl-md flex items-center gap-1.5 py-4 px-5">
        {[0, 1, 2].map((i) => (
          <span
            key={i}
            className="h-2 w-2 rounded-full bg-primary animate-typing-dot"
            style={{ animationDelay: `${i * 0.2}s` }}
          />
        ))}
      </div>
    </motion.div>
  );
}
