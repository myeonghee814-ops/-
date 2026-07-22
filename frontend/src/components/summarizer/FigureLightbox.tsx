import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import type { KeyFigure } from "../../types/summarizer";

interface FigureLightboxProps {
  figure: KeyFigure | null;
  onClose: () => void;
}

export function FigureLightbox({ figure, onClose }: FigureLightboxProps) {
  return (
    <AnimatePresence>
      {figure && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={onClose}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.96 }}
            transition={{ duration: 0.15 }}
            onClick={(e) => e.stopPropagation()}
            className="relative max-h-[85vh] max-w-[90vw] overflow-hidden rounded-2xl bg-card shadow-2xl"
          >
            <button
              type="button"
              onClick={onClose}
              aria-label="닫기"
              className="absolute right-3 top-3 rounded-full bg-black/40 p-1.5 text-white transition-colors hover:bg-black/60"
            >
              <X className="size-4" />
            </button>
            <img src={figure.dataUrl} alt={figure.label} className="max-h-[85vh] max-w-[90vw] object-contain" />
            <div className="border-t border-border px-4 py-2.5 text-center text-sm font-medium text-text">
              {figure.label} <span className="text-subtext">(p.{figure.pageNumber})</span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
