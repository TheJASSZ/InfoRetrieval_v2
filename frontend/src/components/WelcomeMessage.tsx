import { motion } from "framer-motion";
import { Brain, FileText, Image, Bookmark, StickyNote, Globe } from "lucide-react";

const features = [
  { icon: FileText, label: "Documents" },
  { icon: Image, label: "Images" },
  { icon: Bookmark, label: "Bookmarks" },
  { icon: Globe, label: "URLs" },
  { icon: StickyNote, label: "Notes" },
];

export function WelcomeMessage() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: "easeOut" }}
      className="flex flex-col items-center justify-center h-full text-center px-6"
    >
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.2, duration: 0.5 }}
        className="h-16 w-16 rounded-2xl gradient-accent flex items-center justify-center mb-6 glow-primary"
      >
        <Brain className="h-8 w-8 text-primary-foreground" />
      </motion.div>

      <h1 className="text-2xl font-semibold text-foreground mb-2 text-balance">
        Your AI Knowledge Base
      </h1>
      <p className="text-sm text-muted-foreground max-w-md leading-relaxed mb-8">
        Ask me anything about your knowledge base. I can search through your documents, images, bookmarks, and notes.
      </p>

      <div className="flex flex-wrap justify-center gap-3">
        {features.map((f, i) => (
          <motion.div
            key={f.label}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.4 + i * 0.08 }}
            className="stat-pill"
          >
            <f.icon className="h-3.5 w-3.5 text-accent" />
            <span className="text-muted-foreground">{f.label}</span>
          </motion.div>
        ))}
      </div>
    </motion.div>
  );
}
