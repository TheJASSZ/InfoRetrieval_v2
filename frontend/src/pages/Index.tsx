import { useState, useRef, useEffect, useCallback } from "react";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { ChatMessage, ChatMode } from "@/lib/types";
import { StatsBar } from "@/components/StatsBar";
import { ChatMessageBubble, TypingIndicator } from "@/components/ChatMessage";
import { ChatInput } from "@/components/ChatInput";
import { AppSidebar } from "@/components/AppSidebar";
import { WelcomeMessage } from "@/components/WelcomeMessage";

function generateId() {
  return Math.random().toString(36).slice(2, 10);
}

export default function Index() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [mode, setMode] = useState<ChatMode>("chat");
  const [isLoading, setIsLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = useCallback(() => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
    });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading, scrollToBottom]);

  const handleSend = async (text: string) => {
    const userMsg: ChatMessage = {
      id: generateId(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    try {
      if (mode === "chat") {
        const res = await api.chat(text);
        const assistantMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content: res.answer,
          sources: res.sources,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      } else {
        const res = await api.search(text);
        const assistantMsg: ChatMessage = {
          id: generateId(),
          role: "assistant",
          content: `Found **${res.results.length}** results for "${res.query}"`,
          searchResults: res.results,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
      }
    } catch (err: any) {
      toast.error(err.message || "Request failed");
      const errorMsg: ChatMessage = {
        id: generateId(),
        role: "assistant",
        content: "Sorry, I encountered an error processing your request. Please check that the backend is running and try again.",
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <StatsBar />

      <div className="flex-1 flex overflow-hidden relative">
        <AppSidebar />

        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Messages */}
          <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin">
            {messages.length === 0 ? (
              <WelcomeMessage />
            ) : (
              <div className="max-w-4xl mx-auto px-4 py-6">
                {messages.map((msg) => (
                  <ChatMessageBubble key={msg.id} message={msg} />
                ))}
                {isLoading && <TypingIndicator />}
              </div>
            )}
          </div>

          {/* Input */}
          <ChatInput
            onSend={handleSend}
            mode={mode}
            onModeChange={setMode}
            disabled={isLoading}
          />
        </div>
      </div>
    </div>
  );
}
