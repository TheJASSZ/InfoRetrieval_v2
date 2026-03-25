import { useState } from "react";
import { motion } from "framer-motion";
import ReactMarkdown from "react-markdown";
import { ChevronDown, ChevronRight } from "lucide-react";
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

        {/* Sources */}
        {sources.length > 0 && (
          <div className="mt-2">
            <button
              onClick={() => setSourcesOpen(!sourcesOpen)}
              className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
            >
              {sourcesOpen ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              <span>{sources.length} source{sources.length !== 1 ? "s" : ""}</span>
            </button>
            {sourcesOpen && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2"
              >
                {sources.map((s, i) => (
                  <SourceCard key={s.id || i} source={s} />
                ))}
              </motion.div>
            )}
          </div>
        )}

        {/* Search Results */}
        {searchResults.length > 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3"
          >
            {searchResults.map((r, i) => (
              <SourceCard key={r.id || i} source={r} showSummary />
            ))}
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
