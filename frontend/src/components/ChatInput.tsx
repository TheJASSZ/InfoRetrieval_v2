import { useState, useRef, useEffect } from "react";
import { motion } from "framer-motion";
import { Send, Search, MessageSquare } from "lucide-react";
import type { ChatMode } from "@/lib/types";

interface ChatInputProps {
  onSend: (text: string) => void;
  mode: ChatMode;
  onModeChange: (mode: ChatMode) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, mode, onModeChange, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 150) + "px";
    }
  }, [text]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay: 0.2 }}
      className="border-t border-white/[0.06] p-4 glass-strong"
    >
      <div className="max-w-4xl mx-auto flex items-end gap-3">
        {/* Mode toggle */}
        <button
          onClick={() => onModeChange(mode === "chat" ? "search" : "chat")}
          className="flex-shrink-0 glass rounded-xl p-2.5 hover:border-white/[0.12] transition-all group"
          title={mode === "chat" ? "Switch to Search" : "Switch to Chat"}
        >
          {mode === "chat" ? (
            <MessageSquare className="h-4 w-4 text-primary group-hover:scale-110 transition-transform" />
          ) : (
            <Search className="h-4 w-4 text-accent group-hover:scale-110 transition-transform" />
          )}
        </button>

        {/* Input */}
        <div className="flex-1 glass rounded-2xl flex items-end px-4 py-2 focus-within:border-primary/30 focus-within:glow-primary transition-all duration-300">
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={mode === "chat" ? "Ask your knowledge base..." : "Search your knowledge base..."}
            disabled={disabled}
            rows={1}
            className="flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground resize-none outline-none py-1 scrollbar-thin max-h-[150px]"
          />
          <button
            onClick={handleSubmit}
            disabled={disabled || !text.trim()}
            className="flex-shrink-0 ml-2 p-2 rounded-xl gradient-accent text-primary-foreground disabled:opacity-30 hover:opacity-90 transition-all active:scale-95"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="max-w-4xl mx-auto mt-2 flex items-center gap-2">
        <span className="text-[10px] text-muted-foreground/60">
          {mode === "chat" ? "💬 Chat mode — RAG Q&A" : "🔍 Search mode — Semantic search"}
        </span>
      </div>
    </motion.div>
  );
}
